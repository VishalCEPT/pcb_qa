"""
RAG retrieval evaluation: Recall@K, Precision@K, and MRR for the datasheet
retrieval pipeline (core.tool_caller).

Ground truth / relevance definition
------------------------------------
The question datasets (Boards/<board>/Input_Files/*_questions.json) label
each question with a YES/NO answer, not which passage was used to derive
it -- there are no human-labeled per-chunk relevance judgments to evaluate
against. Building new ones would need a separate annotation effort, so
instead this module uses the standard fallback for that situation: document-
level relevance. Each "component_datasheet" category question names exactly
one component (e.g. "component Q2"), and that component has exactly one
correct datasheet among the board's several. A retrieved chunk is "relevant"
if it came from that correct datasheet rather than one of the others. This
is only measurable when retrieval is allowed to search *all* of a board's
datasheets (core.tool_caller.ToolCaller.get_relevant_context_across_all_datasheets);
the normal Q&A/benchmark tool-calling path is told the correct datasheet up
front via component_ref, so it can't be evaluated this way.

Because each question has exactly one relevant document, recall@k is binary
per question (1.0 if the correct datasheet appears anywhere in the top-k,
else 0.0) rather than a fraction over multiple relevant items.
"""

from dataclasses import dataclass, field


@dataclass
class RetrievalResult:
    """One question's cross-datasheet retrieval outcome."""
    question: str
    correct_datasheet: str
    # Ordered best-first; one entry per retrieved chunk (may contain repeats
    # if multiple top-k chunks came from the same datasheet).
    retrieved_datasheets: list[str] = field(default_factory=list)


@dataclass
class RagMetrics:
    recall_at_k: float
    precision_at_k: float
    mrr: float
    k: int
    num_questions: int


def _relevance_mask(result: RetrievalResult) -> list[bool]:
    return [datasheet == result.correct_datasheet for datasheet in result.retrieved_datasheets]


def recall_at_k(result: RetrievalResult) -> float:
    """1.0 if the correct datasheet appears anywhere in the top-k retrieved chunks, else 0.0."""
    mask = _relevance_mask(result)
    return 1.0 if any(mask) else 0.0


def precision_at_k(result: RetrievalResult) -> float:
    """Fraction of the top-k retrieved chunks that came from the correct datasheet."""
    mask = _relevance_mask(result)
    return (sum(mask) / len(mask)) if mask else 0.0


def reciprocal_rank(result: RetrievalResult) -> float:
    """1/rank of the first retrieved chunk from the correct datasheet; 0.0 if none match."""
    for rank, is_relevant in enumerate(_relevance_mask(result), start=1):
        if is_relevant:
            return 1.0 / rank
    return 0.0


def evaluate_retrieval(results: list[RetrievalResult]) -> RagMetrics:
    """Aggregate Recall@K, Precision@K, and MRR over a list of per-question retrieval results."""
    if not results:
        return RagMetrics(recall_at_k=0.0, precision_at_k=0.0, mrr=0.0, k=0, num_questions=0)

    k = max((len(r.retrieved_datasheets) for r in results), default=0)
    recalls = [recall_at_k(r) for r in results]
    precisions = [precision_at_k(r) for r in results]
    reciprocal_ranks = [reciprocal_rank(r) for r in results]

    return RagMetrics(
        recall_at_k=sum(recalls) / len(recalls),
        precision_at_k=sum(precisions) / len(precisions),
        mrr=sum(reciprocal_ranks) / len(reciprocal_ranks),
        k=k,
        num_questions=len(results),
    )
