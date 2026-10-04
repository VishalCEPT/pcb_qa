from google import genai
import os
import json

client = genai.Client(
    api_key=os.environ["GEMINI_API_KEY"]
)

pdf_path = r"outputs\stack-chan\m5-pantilt.pdf"
questions_path = r"outputs\stack-chan\m5-pantilt_60_questions.json"

# Load the benchmark questions
with open(questions_path, "r", encoding="utf-8") as f:
    all_questions = json.load(f)

# Select only the theory/layout questions
questions = [
    q for q in all_questions
    if q["category"] == "theory_layout"
]

print("Theory/layout questions:", len(questions))

# Load schematic PDF
with open(pdf_path, "rb") as f:
    pdf_data = f.read()

results = []

for i, item in enumerate(questions, start=1):

    question = item["question"]
    expected = item["answer"]

    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=[
            {
                "inline_data": {
                    "mime_type": "application/pdf",
                    "data": pdf_data,
                }
            },
            question
        ]
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
output_path = "gemini_pdf_20_results.json"

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print("\n--------------------------------")
print("Experiment completed.")
print("Results saved to:", output_path)