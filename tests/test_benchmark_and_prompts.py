import json
import os
import types as pytypes

import pytest

from backend import benchmark_service, paths
from backend.errors import BoardFileMissingError

prompt_strategies = benchmark_service.prompt_strategies


@pytest.mark.parametrize("text, verdict", [
    ("YES, it is connected.", "YES"),
    ("  yes", "YES"),
    ("**YES** because...", "YES"),
    ("NO. The net is floating.", "NO"),
    ("**No**", "NO"),
    ("It depends.", "UNKNOWN"),
    ("", "UNKNOWN"),
    (None, "UNKNOWN"),
])
def test_parse_yes_no(text, verdict):
    assert prompt_strategies.parse_yes_no(text) == verdict


def test_circuit_json_prompt_contains_question_and_data(monkeypatch):
    seen = {}

    def fake_generate(contents, **_kw):
        seen["prompt"] = contents
        return pytypes.SimpleNamespace(text="NO, it is not.")

    monkeypatch.setattr(prompt_strategies.gemini_client, "generate_content", fake_generate)

    verdict = prompt_strategies.answer_with_circuit_json("Is R1 on GND?", {"components": {"R1": {}}})

    assert verdict == "NO"
    assert "Is R1 on GND?" in seen["prompt"]
    assert '"R1"' in seen["prompt"]


def test_score_pins_labels_so_unknown_does_not_shift_confusion_matrix():
    QR = benchmark_service.QuestionResult
    results = [
        QR(1, "q", "YES", "YES", True),
        QR(2, "q", "YES", "NO", False),
        QR(3, "q", "NO", "UNKNOWN", False),
    ]
    accuracy, _p, _r, _f1, confusion = benchmark_service._score(results)

    assert accuracy == pytest.approx(1 / 3)
    assert confusion == [[1, 1], [0, 0]]


def test_score_empty():
    assert benchmark_service._score([]) == (0.0, 0.0, 0.0, 0.0, [])


@pytest.mark.parametrize("question, expected", [
    ("Does the component Q2 have a flash?", "Q2.pdf"),
    ("Is U1 rated for 5V?", "U1.pdf"),
    ("Does Q12 exist?", None),
    ("Is U10 rated for 5V?", None),
])
def test_component_for_question_uses_whole_ref(question, expected):
    datasheets = [f"/ds/{n}" for n in ("Q1.pdf", "Q2.pdf", "Q2_auto_test.pdf", "U1.pdf")]
    match = benchmark_service._component_for_question(question, datasheets)
    assert (os.path.basename(match) if match else None) == expected


def test_list_categories(board):
    assert benchmark_service.list_categories(board) == ["component_datasheet", "spice_behaviour", "theory_layout"]


def test_run_benchmark_scores_and_persists(board, monkeypatch):
    monkeypatch.setattr(prompt_strategies, "answer_with_circuit_json", lambda _q, _c: "YES")

    report = benchmark_service.run_benchmark(board, "circuit_json", limit=5)

    assert len(report.results) == 5
    assert all(r.predicted == "YES" for r in report.results)
    assert report.accuracy == pytest.approx(sum(r.expected == "YES" for r in report.results) / 5)

    with open(report.results_path) as f:
        saved = json.load(f)
    assert saved["strategy"] == "circuit_json"
    assert len(saved["results"]) == 5


def test_run_benchmark_filters_by_strategy_category(board, monkeypatch):
    seen = []
    monkeypatch.setattr(
        prompt_strategies, "answer_with_datasheet_pdf",
        lambda q, path: seen.append((q, os.path.basename(path))) or "NO",
    )

    report = benchmark_service.run_benchmark(board, "datasheet_pdf")

    with open(paths.find_questions_file(board)) as f:
        questions = json.load(f)
    expected_count = sum(q["category"] == "component_datasheet" for q in questions)
    assert len(report.results) == expected_count
    for question, datasheet in seen:
        assert os.path.splitext(datasheet)[0] in question


def test_run_benchmark_reports_progress_per_question(board, monkeypatch):
    monkeypatch.setattr(prompt_strategies, "answer_with_circuit_json", lambda _q, _c: "YES")
    seen = []

    report = benchmark_service.run_benchmark(
        board, "circuit_json", limit=3, on_question=lambda result, total: seen.append((result, total))
    )

    assert [result for result, _total in seen] == report.results
    assert [total for _result, total in seen] == [3, 3, 3]


def test_spice_strategy_requires_simulation_results(board):
    with pytest.raises(BoardFileMissingError):
        benchmark_service.run_benchmark(board, "spice_json", limit=1)


def test_unknown_strategy(board):
    with pytest.raises(ValueError):
        benchmark_service.run_benchmark(board, "telepathy")


def test_run_benchmark_tool_calling_computes_rag_metrics(board, monkeypatch):
    monkeypatch.setattr(prompt_strategies, "answer_with_tool_calling", lambda _board, _q: "YES")

    def fake_retrieval(question, datasheets, k=3):
        # Every question's correct datasheet retrieved first -> perfect
        # retrieval, so Recall@K/MRR should come out to exactly 1.0.
        correct = benchmark_service._component_for_question(question, datasheets)
        name = os.path.splitext(os.path.basename(correct))[0] if correct else "NONE"
        return [{"datasheet": name, "text": "...", "distance": 0.0}]

    monkeypatch.setattr(
        benchmark_service.ToolCaller, "get_relevant_context_across_all_datasheets",
        lambda self, question, datasheets, k=3: fake_retrieval(question, datasheets, k),
    )

    report = benchmark_service.run_benchmark(board, "tool_calling", limit=10)

    assert report.rag is not None
    assert report.rag.num_questions > 0
    assert report.rag.recall_at_k == 1.0
    assert report.rag.mrr == 1.0

    with open(report.results_path) as f:
        saved = json.load(f)
    assert saved["rag_metrics"]["recall_at_k"] == 1.0


def test_run_benchmark_non_tool_calling_strategy_has_no_rag_metrics(board, monkeypatch):
    monkeypatch.setattr(prompt_strategies, "answer_with_circuit_json", lambda _q, _c: "YES")

    report = benchmark_service.run_benchmark(board, "circuit_json", limit=3)

    assert report.rag is None
    with open(report.results_path) as f:
        saved = json.load(f)
    assert "rag_metrics" not in saved
