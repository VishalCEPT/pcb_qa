"""
Interactive LLM Q&A facade.

Wires Gemini's native function-calling against the existing
core.tool_caller.ToolCaller (SPICE steady-state voltage check, net/component
connection check, and RAG datasheet lookup), so the GUI's Q&A tab can ask a
free-form question about a board and see both the final answer and which
tools were used to produce it.
"""

import os
from dataclasses import dataclass, field

from google.genai import types
from tool_caller import ToolCaller

from backend import board_service, gemini_client, observability, paths

# File-path arguments are deliberately not exposed to Gemini: it can't know the
# real on-disk paths and would hallucinate them. _inject_board_paths() supplies
# the selected board's paths before each tool call instead.
_SPICE_TOOL = types.FunctionDeclaration(
    name="calculate_spice_behaviour",
    description=(
        "Check whether a net's steady-state voltage from the SPICE simulation "
        "matches an expected value."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "net_name": types.Schema(type="STRING", description="Net name, e.g. +3V3, GND"),
            "expected_voltage": types.Schema(type="STRING", description="Expected voltage, e.g. 3.3V"),
        },
        required=["net_name", "expected_voltage"],
    ),
)

_CONNECTIONS_TOOL = types.FunctionDeclaration(
    name="find_connections_for_component",
    description="Check whether a component is connected to a given net in the board layout.",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "component_ref": types.Schema(type="STRING", description="Reference designator, e.g. R1, U2"),
            "net_name": types.Schema(type="STRING", description="Net name, e.g. GND, VCC"),
        },
        required=["component_ref", "net_name"],
    ),
)

_DATASHEET_TOOL = types.FunctionDeclaration(
    name="get_relevant_context_from_question",
    description="Retrieve relevant datasheet excerpts for a component to help answer a question.",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "question": types.Schema(type="STRING", description="The question to answer"),
            "component_ref": types.Schema(type="STRING", description="Reference designator, e.g. R1, U2"),
        },
        required=["question", "component_ref"],
    ),
)

_TOOL_PATH_ARGS = {
    "calculate_spice_behaviour": ["spice_json_file"],
    "find_connections_for_component": ["circuit_json_file"],
    "get_relevant_context_from_question": ["project_context"],
}

_TOOLS = [types.Tool(function_declarations=[_SPICE_TOOL, _CONNECTIONS_TOOL, _DATASHEET_TOOL])]

_MAX_TOOL_TURNS = 4


@dataclass
class ToolCallRecord:
    name: str
    args: dict
    result: object


@dataclass
class QAResult:
    answer: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)


def _project_context(board_name: str) -> dict:
    circuit = board_service.load_or_generate_circuit(board_name)
    return {
        "circuit_json_file": circuit.circuit_json_path,
        "spice_json_file": paths.spice_json_path(board_name),
        "datasheet_files": paths.find_datasheets(board_name),
    }


def _inject_board_paths(tool_name: str, llm_args: dict, project_context: dict) -> dict:
    args = {k: v for k, v in llm_args.items() if k not in _TOOL_PATH_ARGS.get(tool_name, [])}
    if tool_name == "get_relevant_context_from_question":
        args["project_context"] = project_context
    elif tool_name == "calculate_spice_behaviour":
        args["spice_json_file"] = project_context["spice_json_file"]
    elif tool_name == "find_connections_for_component":
        args["circuit_json_file"] = project_context["circuit_json_file"]
    return args


def _model_turn(response):
    """The model's turn (to echo back verbatim) and the function calls it makes."""
    content = response.candidates[0].content
    return content, [part.function_call for part in content.parts or [] if part.function_call]


def _run_tool(tool_caller: ToolCaller, function_call, project_context: dict) -> ToolCallRecord:
    args = _inject_board_paths(function_call.name, dict(function_call.args or {}), project_context)

    with observability.observation("tool", name=function_call.name, input=args) as tool_span:
        handler = tool_caller.available_functions.get(function_call.name)
        if handler is None:
            result = {"error": f"Unknown tool '{function_call.name}'"}
        elif function_call.name == "calculate_spice_behaviour" and not os.path.exists(args["spice_json_file"]):
            # The tool would return False here, which reads as "voltage doesn't match".
            result = {"error": "No SPICE simulation results exist for this board yet, so voltages can't be checked."}
        else:
            try:
                result = handler(**args)
            except TypeError as exc:
                result = {"error": str(exc)}

        tool_span.update(output=result)

    return ToolCallRecord(name=function_call.name, args=args, result=result)


def ask(board_name: str, question: str, on_tool_call=None) -> QAResult:
    """
    Ask a free-form engineering question about a board. Gemini may call any of
    ToolCaller's three tools against this board's real files before giving a
    final natural-language answer; each call made is recorded on the result.

    If `on_tool_call` is given, it's called as `on_tool_call(record)` right
    after each tool call completes, so a caller can show live progress.
    """
    tool_caller = ToolCaller()
    project_context = _project_context(board_name)

    contents = [types.Content(role="user", parts=[types.Part.from_text(text=question)])]
    tool_calls: list[ToolCallRecord] = []

    with observability.observation("chain", name="qa.ask", input={"board": board_name, "question": question}) as chain:
        for _ in range(_MAX_TOOL_TURNS):
            response = gemini_client.generate_content(contents=contents, tools=_TOOLS)
            model_content, function_calls = _model_turn(response)

            if not function_calls:
                chain.update(output=response.text or "")
                return QAResult(answer=response.text or "", tool_calls=tool_calls)

            records = [_run_tool(tool_caller, call, project_context) for call in function_calls]
            tool_calls.extend(records)
            if on_tool_call is not None:
                for record in records:
                    on_tool_call(record)

            # Echo the model's turn back unmodified: Gemini 3 rejects function calls
            # whose thought_signature was dropped by rebuilding the part.
            contents.append(model_content)
            contents.append(types.Content(
                role="user",
                parts=[
                    types.Part.from_function_response(name=record.name, response={"result": record.result})
                    for record in records
                ],
            ))

        chain.update(output="Reached the maximum number of tool-call turns without a final answer.")
        return QAResult(
            answer="Reached the maximum number of tool-call turns without a final answer.",
            tool_calls=tool_calls,
        )
