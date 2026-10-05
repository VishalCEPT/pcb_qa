"""
Benchmark & evaluation facade for the GUI's Benchmark tab.

Runs a board's question bank (Boards/<board>/Input_Files/*_questions.json)
through one of the prompt-engineering strategies in
llm_evaluation/prompt_strategies.py, scores the YES/NO predictions with the
same sklearn metrics evaluation/evaluate_results.py uses (labels pinned to
["YES", "NO"], zero_division=0 so an unparseable response doesn't silently
change confusion-matrix semantics), and persists the results under
Boards/<board>/Output_Files/benchmark_results/.
"""

import os
import re
import sys
from dataclasses import dataclass, field
from enum import Enum

from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score

import file_helpers
from tool_caller import ToolCaller

from backend import board_service, observability, paths
from backend.errors import BoardFileMissingError
from evaluation import rag_metrics

_LLM_EVAL_DIR = os.path.join(paths.REPO_ROOT, "llm_evaluation")
if _LLM_EVAL_DIR not in sys.path:
    sys.path.insert(0, _LLM_EVAL_DIR)

import prompt_strategies  # noqa: E402


class Strategy(str, Enum):
    SCHEMATIC_PDF = "schematic_pdf"
    CIRCUIT_JSON = "circuit_json"
    SPICE_JSON = "spice_json"
    DATASHEET_PDF = "datasheet_pdf"
    TOOL_CALLING = "tool_calling"


_STRATEGY_CATEGORY = {
    Strategy.SCHEMATIC_PDF: "theory_layout",
    Strategy.CIRCUIT_JSON: "theory_layout",
    Strategy.SPICE_JSON: "spice_behaviour",
    Strategy.DATASHEET_PDF: "component_datasheet",
}


@dataclass
class QuestionResult:
    question_number: int
    question: str
    expected: str
    predicted: str
    correct: bool


@dataclass
class BenchmarkReport:
    board_name: str
    strategy: str
    results: list[QuestionResult] = field(default_factory=list)
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    confusion: list = field(default_factory=list)
    results_path: str = ""
    # Only populated for Strategy.TOOL_CALLING (the only strategy whose
    # answers actually depend on the FAISS datasheet-retrieval pipeline);
    # None for every other strategy.
    rag: rag_metrics.RagMetrics | None = None


def list_strategies() -> list[str]:
    return [s.value for s in Strategy]


def _load_questions(board_name: str) -> list[dict]:
    questions_path = paths.find_questions_file(board_name)
    if questions_path is None:
        raise BoardFileMissingError(
            f"Board '{board_name}' has no *_questions.json file under {paths.input_dir(board_name)}"
        )
    return file_helpers.JSONFileOperator().read_from_json_file(questions_path)


def list_categories(board_name: str) -> list[str]:
    return sorted({q["category"] for q in _load_questions(board_name)})


def _component_for_question(question: str, datasheets: list[str]) -> str | None:
    for path in datasheets:
        ref = os.path.splitext(os.path.basename(path))[0]
        if re.search(rf"\b{re.escape(ref)}\b", question):
            return path
    return None


def _score(results: list[QuestionResult]) -> tuple[float, float, float, float, list]:
    if not results:
        return 0.0, 0.0, 0.0, 0.0, []

    expected = [r.expected for r in results]
    predicted = [r.predicted for r in results]

    accuracy = accuracy_score(expected, predicted)
    precision = precision_score(expected, predicted, labels=["YES", "NO"], average="macro", zero_division=0)
    recall = recall_score(expected, predicted, labels=["YES", "NO"], average="macro", zero_division=0)
    f1 = f1_score(expected, predicted, labels=["YES", "NO"], average="macro", zero_division=0)
    confusion = confusion_matrix(expected, predicted, labels=["YES", "NO"]).tolist()

    return accuracy, precision, recall, f1, confusion


def run_benchmark(
    board_name: str, strategy: str, limit: int | None = None, on_question=None
) -> BenchmarkReport:
    """
    Run every question in the strategy's category (or the first `limit` of
    them) through that strategy, score the YES/NO predictions, and persist
    the results as JSON under Boards/<board>/Output_Files/benchmark_results/.

    If `on_question` is given, it's called as `on_question(result, total)`
    right after each question is scored, so a caller can show live progress.

    The whole run is wrapped in a Langfuse trace (a no-op if Langfuse isn't
    configured -- see backend.observability) so every Gemini generation and
    datasheet retrieval call made along the way shows up nested under it in
    the dashboard, with the final accuracy/F1/RAG metrics attached as scores.
    """
    strategy = Strategy(strategy)
    questions = _load_questions(board_name)

    category = _STRATEGY_CATEGORY.get(strategy)
    if category is not None:
        questions = [q for q in questions if q["category"] == category]
    if limit is not None:
        questions = questions[:limit]

    circuit = spice_json = pdf_path = datasheets = None

    if strategy == Strategy.CIRCUIT_JSON:
        circuit = board_service.load_or_generate_circuit(board_name).circuit
    elif strategy == Strategy.SPICE_JSON:
        spice_json_path = paths.spice_json_path(board_name)
        if not os.path.exists(spice_json_path):
            raise BoardFileMissingError(
                f"No SPICE simulation results for '{board_name}'. Run the SPICE simulation first."
            )
        spice_json = file_helpers.JSONFileOperator().read_from_json_file(spice_json_path)
    elif strategy == Strategy.SCHEMATIC_PDF:
        pdf_path = paths.find_schematic_pdf(board_name)
        if pdf_path is None:
            raise BoardFileMissingError(f"Board '{board_name}' has no schematic PDF under {paths.input_dir(board_name)}")
    elif strategy == Strategy.DATASHEET_PDF:
        datasheets = paths.find_datasheets(board_name)
    elif strategy == Strategy.TOOL_CALLING:
        datasheets = paths.find_datasheets(board_name)

    with observability.observation(
        "span", name=f"benchmark.{strategy.value}",
        input={"board": board_name, "strategy": strategy.value, "num_questions": len(questions)},
    ) as trace:
        results: list[QuestionResult] = []

        for i, item in enumerate(questions, start=1):
            question = item["question"]
            expected = item["answer"]

            if strategy == Strategy.SCHEMATIC_PDF:
                predicted = prompt_strategies.answer_with_schematic_pdf(question, pdf_path)
            elif strategy == Strategy.CIRCUIT_JSON:
                predicted = prompt_strategies.answer_with_circuit_json(question, circuit)
            elif strategy == Strategy.SPICE_JSON:
                predicted = prompt_strategies.answer_with_spice_json(question, spice_json)
            elif strategy == Strategy.DATASHEET_PDF:
                datasheet_path = _component_for_question(question, datasheets)
                predicted = (
                    prompt_strategies.answer_with_datasheet_pdf(question, datasheet_path)
                    if datasheet_path else "UNKNOWN"
                )
            else:  # Strategy.TOOL_CALLING
                predicted = prompt_strategies.answer_with_tool_calling(board_name, question)

            results.append(QuestionResult(
                question_number=i,
                question=question,
                expected=expected,
                predicted=predicted,
                correct=predicted == expected,
            ))
            if on_question is not None:
                on_question(results[-1], len(questions))

        accuracy, precision, recall, f1, confusion = _score(results)

        rag_report = None
        if strategy == Strategy.TOOL_CALLING and datasheets:
            rag_report = _evaluate_rag_retrieval(questions, datasheets)

        trace.score_trace(name="accuracy", value=accuracy)
        trace.score_trace(name="precision", value=precision)
        trace.score_trace(name="recall", value=recall)
        trace.score_trace(name="f1", value=f1)
        if rag_report is not None:
            trace.score_trace(name="rag_recall_at_k", value=rag_report.recall_at_k)
            trace.score_trace(name="rag_precision_at_k", value=rag_report.precision_at_k)
            trace.score_trace(name="rag_mrr", value=rag_report.mrr)
        trace.update(output={"accuracy": accuracy, "f1": f1})

    results_path = os.path.join(paths.benchmark_results_dir(board_name), f"{strategy.value}.json")
    saved = {
        "board_name": board_name,
        "strategy": strategy.value,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "confusion_matrix": confusion,
        "results": [vars(r) for r in results],
    }
    if rag_report is not None:
        saved["rag_metrics"] = vars(rag_report)
    file_helpers.JSONFileOperator().write_to_json_file(saved, results_path)

    return BenchmarkReport(
        board_name=board_name,
        strategy=strategy.value,
        results=results,
        accuracy=accuracy,
        precision=precision,
        recall=recall,
        f1=f1,
        confusion=confusion,
        results_path=results_path,
        rag=rag_report,
    )


def _evaluate_rag_retrieval(questions: list[dict], datasheets: list[str]) -> rag_metrics.RagMetrics | None:
    """
    Measure retrieval quality (Recall@K/Precision@K/MRR) for the
    "component_datasheet" category questions in `questions`, searching
    across all of `datasheets` rather than the single correct one the real
    answer-generation path is told up front -- see evaluation.rag_metrics
    for why document-level relevance is the ground truth used here.
    """
    component_questions = [q for q in questions if q["category"] == "component_datasheet"]
    if not component_questions:
        return None

    tool_caller = ToolCaller()
    retrieval_results = []

    for item in component_questions:
        question = item["question"]
        datasheet_path = _component_for_question(question, datasheets)
        if datasheet_path is None:
            continue

        correct_datasheet = os.path.splitext(os.path.basename(datasheet_path))[0]
        retrieved = tool_caller.get_relevant_context_across_all_datasheets(question, datasheets, k=3)

        retrieval_results.append(rag_metrics.RetrievalResult(
            question=question,
            correct_datasheet=correct_datasheet,
            retrieved_datasheets=[r["datasheet"] for r in retrieved],
        ))

    return rag_metrics.evaluate_retrieval(retrieval_results) if retrieval_results else None

