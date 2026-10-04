from google import genai
import os
import json

client = genai.Client(
    api_key=os.environ["GEMINI_API_KEY"]
)

json_path = r"outputs\stack-chan\m5-pantilt.json"
questions_path = r"outputs\stack-chan\m5-pantilt_60_questions.json"

# Load the benchmark questions
with open(questions_path, "r", encoding="utf-8") as f:
    all_questions = json.load(f)

# Select the exact same 20 theory/layout questions
questions = [
    q for q in all_questions
    if q["category"] == "theory_layout"
]

print("Theory/layout questions:", len(questions))

# Load circuit JSON
with open(json_path, "r", encoding="utf-8") as f:
    circuit_data = json.load(f)

# Convert circuit JSON to text for Gemini
circuit_text = json.dumps(circuit_data, indent=2)

results = []

for i, item in enumerate(questions, start=1):

    question = item["question"]
    expected = item["answer"]

    prompt = f"""
You are analyzing a PCB circuit represented as structured JSON.

Circuit data:
{circuit_text}

Question:
{question}

Answer with YES or NO first, followed by a short explanation.
"""

    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=prompt
    )

    answer = response.text.strip()

    print(f"\nQuestion {i}:")
    print(question)

    print("Expected:")
    print(expected)

    print("Gemini:")
    print(answer)

    results.append({
        "question_number": i,
        "category": item["category"],
        "question": question,
        "expected_answer": expected,
        "gemini_response": answer
    })

# Save results separately
output_path = "gemini_json_20_results.json"

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print("\n--------------------------------")
print("Experiment completed.")
print("Results saved to:", output_path)