import os
import types as pytypes

import pytest
from google.genai import types
from tool_caller import ToolCaller

from backend import qa_service


def _response(function_call=None, text=None, function_calls=()):
    calls = [function_call] if function_call else list(function_calls)
    parts = [pytypes.SimpleNamespace(function_call=call) for call in calls] or [
        pytypes.SimpleNamespace(function_call=None)
    ]
    candidate = pytypes.SimpleNamespace(content=pytypes.SimpleNamespace(role="model", parts=parts))
    return pytypes.SimpleNamespace(candidates=[candidate], text=text)


def test_inject_board_paths_overrides_llm_supplied_paths():
    ctx = {"circuit_json_file": "/real/c.json", "spice_json_file": "/real/s.json", "datasheet_files": []}

    args = qa_service._inject_board_paths(
        "find_connections_for_component",
        {"component_ref": "R1", "net_name": "GND", "circuit_json_file": "C:/Windows/win.ini"},
        ctx,
    )
    assert args == {"component_ref": "R1", "net_name": "GND", "circuit_json_file": "/real/c.json"}

    args = qa_service._inject_board_paths(
        "get_relevant_context_from_question",
        {"question": "q", "component_ref": "U1", "project_context": {"datasheet_files": ["/etc/passwd"]}},
        ctx,
    )
    assert args["project_context"] is ctx


def test_tool_declarations_do_not_ask_gemini_for_paths():
    for decl in qa_service._TOOLS[0].function_declarations:
        assert not any("file" in name or name == "project_context" for name in decl.parameters.properties)


def test_ask_runs_tool_against_real_board_then_answers(board, allow_tmp_boards, monkeypatch):
    calls = []
    responses = iter([
        _response(function_call=types.FunctionCall(
            name="find_connections_for_component",
            args={"component_ref": "D2", "net_name": "Net__D2_K_", "circuit_json_file": "guessed.json"},
        )),
        _response(text="YES, D2 is connected to Net__D2_K_."),
    ])

    def fake_generate(contents, tools=None, **_kw):
        calls.append(list(contents))
        return next(responses)

    monkeypatch.setattr(qa_service.gemini_client, "generate_content", fake_generate)

    result = qa_service.ask(board, "Is D2 connected to Net__D2_K_?")

    assert result.answer.startswith("YES")
    assert len(result.tool_calls) == 1
    record = result.tool_calls[0]
    assert record.result is True
    assert record.args["circuit_json_file"] != "guessed.json"
    assert os.path.exists(record.args["circuit_json_file"])

    # Second request carried the model's call and our function response.
    assert len(calls[1]) == 3
    assert calls[1][2].parts[0].function_response.response == {"result": True}


def test_ask_echoes_model_turn_and_answers_parallel_calls(board, allow_tmp_boards, monkeypatch):
    calls = []
    first = _response(function_calls=[
        types.FunctionCall(name="find_connections_for_component", args={"component_ref": "R10", "net_name": "PWM1"}),
        types.FunctionCall(name="find_connections_for_component", args={"component_ref": "R1", "net_name": "PWM1"}),
    ])
    responses = iter([first, _response(text="R10 yes, R1 no.")])

    def fake_generate(contents, tools=None, **_kw):
        calls.append(list(contents))
        return next(responses)

    monkeypatch.setattr(qa_service.gemini_client, "generate_content", fake_generate)

    result = qa_service.ask(board, "Are R10 and R1 on PWM1?")

    assert [r.result for r in result.tool_calls] == [True, False]
    # The model's turn is sent back as-is (keeps Gemini 3 thought signatures).
    assert calls[1][1] is first.candidates[0].content
    responses_sent = [p.function_response.response for p in calls[1][2].parts]
    assert responses_sent == [{"result": True}, {"result": False}]


def test_ask_gives_up_after_max_tool_turns(board, allow_tmp_boards, monkeypatch):
    call = types.FunctionCall(name="find_connections_for_component", args={"component_ref": "R1", "net_name": "GND"})
    monkeypatch.setattr(qa_service.gemini_client, "generate_content",
                        lambda contents, tools=None, **_kw: _response(function_call=call))

    result = qa_service.ask(board, "loop forever")

    assert len(result.tool_calls) == qa_service._MAX_TOOL_TURNS
    assert "maximum number of tool-call turns" in result.answer


def test_unknown_tool_is_reported_not_raised(board, allow_tmp_boards, monkeypatch):
    responses = iter([
        _response(function_call=types.FunctionCall(name="rm_rf", args={})),
        _response(text="NO"),
    ])
    monkeypatch.setattr(qa_service.gemini_client, "generate_content",
                        lambda contents, tools=None, **_kw: next(responses))

    result = qa_service.ask(board, "q")
    assert result.tool_calls[0].result == {"error": "Unknown tool 'rm_rf'"}


def test_spice_tool_reports_missing_results_instead_of_false(board, allow_tmp_boards, monkeypatch):
    call = types.FunctionCall(name="calculate_spice_behaviour", args={"net_name": "+3V3", "expected_voltage": 3.3})
    responses = iter([_response(function_call=call), _response(text="UNKNOWN")])
    monkeypatch.setattr(qa_service.gemini_client, "generate_content",
                        lambda contents, tools=None, **_kw: next(responses))

    result = qa_service.ask(board, "Is +3V3 at 3.3 V?")
    assert "No SPICE simulation results" in result.tool_calls[0].result["error"]


def test_ask_calls_on_tool_call_as_each_tool_completes(board, allow_tmp_boards, monkeypatch):
    responses = iter([
        _response(function_call=types.FunctionCall(
            name="find_connections_for_component",
            args={"component_ref": "D2", "net_name": "Net__D2_K_"},
        )),
        _response(text="YES, D2 is connected to Net__D2_K_."),
    ])
    monkeypatch.setattr(qa_service.gemini_client, "generate_content",
                        lambda contents, tools=None, **_kw: next(responses))

    seen = []
    result = qa_service.ask(board, "Is D2 connected to Net__D2_K_?", on_tool_call=seen.append)

    assert seen == result.tool_calls
    assert seen[0].result is True


class TestToolCallerPathConfinement:
    def test_rejects_path_outside_allowed_roots(self, tmp_path):
        outside = tmp_path / "secret.json"
        outside.write_text("{}")
        with pytest.raises(PermissionError):
            ToolCaller._resolve_and_validate_path(str(outside))

    def test_rejects_traversal_out_of_boards(self):
        root = ToolCaller._ALLOWED_ROOT_DIRS[0]
        with pytest.raises(PermissionError):
            ToolCaller._resolve_and_validate_path(os.path.join(root, "..", "core", "tool_caller.py"))

    def test_rejects_sibling_with_shared_prefix(self):
        root = ToolCaller._ALLOWED_ROOT_DIRS[0]
        with pytest.raises(PermissionError):
            ToolCaller._resolve_and_validate_path(root + "_evil" + os.sep + "x.json")

    def test_tool_returns_false_instead_of_reading_outside_file(self, tmp_path):
        outside = tmp_path / "circuit.json"
        outside.write_text('{"components": {"R1": {}}, "nets": {"GND": [{"component": "R1"}]}, "subcircuits": []}')
        assert ToolCaller().find_connections_for_component(str(outside), "R1", "GND") is False
