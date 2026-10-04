from google import genai
from google.genai import types
import os

from tool_caller import ToolCaller


# --------------------------------------------------
# 1. Gemini client
# --------------------------------------------------
client = genai.Client(
    api_key=os.environ["GEMINI_API_KEY"]
)

# --------------------------------------------------
# 2. PCB-QA ToolCaller
# --------------------------------------------------
pcbqa = ToolCaller()


# --------------------------------------------------
# 3. Define PCB-QA SPICE tool for Gemini
# --------------------------------------------------
spice_tool_declaration = types.FunctionDeclaration(
    name="calculate_spice_behaviour",
    description=(
        "Analyse signal behavior in the PCB-QA SPICE simulation "
        "and determine whether a net matches the expected voltage."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "spice_json_file": types.Schema(
                type="STRING",
                description="Path to the PCB-QA SPICE JSON file"
            ),
            "net_name": types.Schema(
                type="STRING",
                description="SPICE net name"
            ),
            "expected_voltage": types.Schema(
                type="STRING",
                description="Expected voltage, for example 3.3V"
            ),
        },
        required=[
            "spice_json_file",
            "net_name",
            "expected_voltage",
        ],
    ),
)

tool = types.Tool(
    function_declarations=[spice_tool_declaration]
)


# --------------------------------------------------
# 4. Ask Gemini
# --------------------------------------------------
question = (
    "Does the +3v3 net have a steady-state voltage "
    "of 3.3V according to the PCB-QA SPICE simulation?"
)

response = client.models.generate_content(
    model="gemini-3.8-flash",
    contents=question,
    config=types.GenerateContentConfig(
        tools=[tool]
    ),
)


# --------------------------------------------------
# 5. Read Gemini's tool selection
# --------------------------------------------------
function_call = None

for candidate in response.candidates:
    for part in candidate.content.parts:
        if part.function_call:
            function_call = part.function_call
            break

    if function_call:
        break


if function_call is None:
    print("Gemini did not request a PCB-QA tool.")
    print(response.text)
    raise SystemExit


print("Gemini selected tool:")
print(function_call.name)

print("\nTool arguments:")
print(function_call.args)


# --------------------------------------------------
# 6. Execute REAL PCB-QA SPICE function
# --------------------------------------------------
tool_result = pcbqa.calculate_spice_behaviour(
    spice_json_file="outputs/stack-chan/m5-pantilt_SPICE_circuit.json",
    net_name=function_call.args["net_name"],
    expected_voltage=function_call.args["expected_voltage"],
)

print("\nPCB-QA tool result:")
print(tool_result)


# --------------------------------------------------
# 7. Ask Gemini for final answer
# --------------------------------------------------
final_response = client.models.generate_content(
    model="gemini-3.8-flash",
    contents=(
        question
        + "\n\nPCB-QA SPICE tool result: "
        + str(tool_result)
        + "\n\nAnswer the original question in one sentence."
    ),
)

print("\nGemini final answer:")
print(final_response.text)