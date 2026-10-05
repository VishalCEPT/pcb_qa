import os

import pytest

from backend import paths
from tool_caller import ToolCaller


@pytest.mark.integration
def test_cross_datasheet_retrieval_finds_correct_datasheet_among_distractors(board, allow_tmp_boards):
    """
    Real (non-mocked) FAISS + sentence-transformers retrieval across all of
    stack-chan's 4 datasheets, searching with a question about a specific,
    identifying characteristic of U1 (its SPI transmit rate). This is the
    same retrieval path evaluation.rag_metrics is built to score, so it's
    worth one real end-to-end check that it actually surfaces the correct
    datasheet (U1.pdf) rather than one of the 3 distractor components'.
    """
    datasheets = paths.find_datasheets(board)
    assert {os.path.splitext(os.path.basename(d))[0] for d in datasheets} == {"Q1", "Q2", "Q2_auto_test", "U1"}

    results = ToolCaller().get_relevant_context_across_all_datasheets(
        "Does the component U1 have a transmit rate of 10Mbps according to its datasheet?",
        datasheets,
        k=3,
    )

    assert results
    assert all({"datasheet", "text", "distance"} <= set(r) for r in results)
    assert "U1" in {r["datasheet"] for r in results}
