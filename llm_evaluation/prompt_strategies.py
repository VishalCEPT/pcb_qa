"""
Shared prompt-engineering strategies for answering PCB-QA benchmark questions
with Gemini: each strategy injects a different kind of context (full
schematic PDF, circuit JSON, SPICE JSON, per-component datasheet PDF, or
native tool-calling) ahead of the question, and parses a YES/NO verdict back
out of the response text.

This consolidates logic that used to be duplicated across 5 near-identical
test_gemini_*_20.py scripts in this directory, each of which called
generate_content directly with no retry/backoff (a single transient API
error lost the whole in-memory results list for that run). All 5 strategies
now go through backend.gemini_client, which has retry/backoff built in.
"""

import json

from backend import gemini_client, qa_service

_YES_NO_INSTRUCTION = "Answer with YES or NO first, followed by a short explanation."


def parse_yes_no(response_text: str) -> str:
    """Pull a YES/NO/UNKNOWN verdict out of the start of a Gemini response."""
    upper = (response_text or "").strip().upper()
    if upper.startswith("YES") or upper.startswith("**YES"):
        return "YES"
    if upper.startswith("NO") or upper.startswith("**NO"):
        return "NO"
    return "UNKNOWN"


def answer_with_circuit_json(question: str, circuit_json: dict) -> str:
    prompt = (
        "You are analyzing a PCB circuit represented as structured JSON.\n\n"
        f"Circuit data:\n{json.dumps(circuit_json, indent=2)}\n\n"
        f"Question:\n{question}\n\n{_YES_NO_INSTRUCTION}"
    )
    response = gemini_client.generate_content(contents=prompt)
    return parse_yes_no(response.text)


def answer_with_spice_json(question: str, spice_json: dict) -> str:
    prompt = (
        "You are analyzing the simulated behaviour of a PCB circuit.\n\n"
        "The following is the structured SPICE simulation data:\n"
        f"{json.dumps(spice_json, indent=2)}\n\n"
        f"Question:\n{question}\n\n{_YES_NO_INSTRUCTION}"
    )
    response = gemini_client.generate_content(contents=prompt)
    return parse_yes_no(response.text)


def answer_with_schematic_pdf(question: str, pdf_path: str) -> str:
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    contents = [
        {"inline_data": {"mime_type": "application/pdf", "data": pdf_bytes}},
        f"{question}\n\n{_YES_NO_INSTRUCTION}",
    ]
    response = gemini_client.generate_content(contents=contents)
    return parse_yes_no(response.text)


def answer_with_datasheet_pdf(question: str, datasheet_path: str) -> str:
    with open(datasheet_path, "rb") as f:
        pdf_bytes = f.read()
    contents = [
        {"inline_data": {"mime_type": "application/pdf", "data": pdf_bytes}},
        (
            "Answer the following question using only the provided datasheet. "
            f"{_YES_NO_INSTRUCTION}\n\n{question}"
        ),
    ]
    response = gemini_client.generate_content(contents=contents)
    return parse_yes_no(response.text)


def answer_with_tool_calling(board_name: str, question: str) -> str:
    result = qa_service.ask(board_name, f"{question}\n\n{_YES_NO_INSTRUCTION}")
    return parse_yes_no(result.answer)
