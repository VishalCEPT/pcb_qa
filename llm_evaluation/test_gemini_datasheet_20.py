from google import genai
import os
import json

client = genai.Client(
    api_key=os.environ["GEMINI_API_KEY"]
)

# Official PCB-QA benchmark questions
questions_path = r"outputs\stack-chan\m5-pantilt_60_questions.json"

# Datasheets used by the m5-pantilt board
datasheet_paths = {
    "Q1": r"outputs\stack-chan\datasheets\Q1.pdf",
    "Q2": r"outputs\stack-chan\datasheets\Q2.pdf",
    "U1": r"outputs\stack-chan\datasheets\U1.pdf",
}

# Load benchmark
with open(questions_path, "r", encoding="utf-8") as f:
    benchmark = json.load(f)

# Select only component_datasheet questions
datasheet_questions = [
    q for q in benchmark
    if q.get("category") == "component_datasheet"
]

print(f"Found {len(datasheet_questions)} component_datasheet questions")

results = []

for i, q in enumerate(datasheet_questions, start=1):

    question = q["question"]
    expected = q["answer"]

    # Determine component from question
    component = None

    for ref in ["Q1", "Q2", "U1"]:
        if ref in question:
            component = ref
            break

    if component is None:
        print(f"\nSkipping Q{i}: could not identify component")
        continue

    pdf_path = datasheet_paths[component]

    with open(pdf_path, "rb") as f:
        pdf_data = f.read()

    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=[
            {
                "inline_data": {
                    "mime_type": "application/pdf",
                    "data": pdf_data,
                }
            },
            (
                "Answer the following question using only the provided "
                "datasheet. Respond with YES or NO first, followed by a "
                "short explanation.\n\n"
                + question
            )
        ]
    )

    answer_text = response.text.strip()

    # Determine predicted YES/NO from beginning of response
    upper_response = answer_text.upper().strip()

    if upper_response.startswith("YES") or upper_response.startswith("**YES"):
        predicted = "YES"
    elif upper_response.startswith("NO") or upper_response.startswith("**NO"):
        predicted = "NO"
    else:
        predicted = "UNKNOWN"

    correct = predicted == expected

    print(f"\n[{i}/20]")
    print(f"Component : {component}")
    print(f"Question  : {question}")
    print(f"Expected  : {expected}")
    print(f"Predicted : {predicted}")
    print(f"Correct   : {correct}")
    print(f"Response  : {answer_text}")

    results.append({
        "question_number": i,
        "component": component,
        "question": question,
        "expected": expected,
        "predicted": predicted,
        "correct": correct,
        "response": answer_text,
    })


# Summary
correct_count = sum(r["correct"] for r in results)
total = len(results)

print("\n" + "=" * 60)
print("DATASHEET BASELINE RESULTS")
print("=" * 60)
print(f"Correct : {correct_count}/{total}")
print(f"Accuracy: {correct_count / total * 100:.2f}%")

# Save results
output_path = "gemini_datasheet_20_results.json"

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

print(f"\nResults saved to: {output_path}")