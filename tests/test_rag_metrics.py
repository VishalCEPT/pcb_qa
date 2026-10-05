import pytest

from evaluation import rag_metrics


def _result(correct, retrieved):
    return rag_metrics.RetrievalResult(question="q", correct_datasheet=correct, retrieved_datasheets=retrieved)


class TestPerQuestionMetrics:
    def test_recall_hit_at_any_rank(self):
        assert rag_metrics.recall_at_k(_result("U2", ["U1", "U2", "U3"])) == 1.0
        assert rag_metrics.recall_at_k(_result("U2", ["U2", "U1", "U3"])) == 1.0

    def test_recall_miss(self):
        assert rag_metrics.recall_at_k(_result("U2", ["U1", "U3", "U4"])) == 0.0

    def test_recall_empty_retrieval(self):
        assert rag_metrics.recall_at_k(_result("U2", [])) == 0.0

    def test_precision_counts_matching_fraction(self):
        assert rag_metrics.precision_at_k(_result("U2", ["U2", "U2", "U1"])) == pytest.approx(2 / 3)
        assert rag_metrics.precision_at_k(_result("U2", ["U1", "U3", "U4"])) == 0.0
        assert rag_metrics.precision_at_k(_result("U2", ["U2", "U2", "U2"])) == 1.0

    def test_precision_empty_retrieval(self):
        assert rag_metrics.precision_at_k(_result("U2", [])) == 0.0

    @pytest.mark.parametrize("retrieved, expected_rr", [
        (["U2", "U1", "U3"], 1.0),
        (["U1", "U2", "U3"], 0.5),
        (["U1", "U3", "U2"], pytest.approx(1 / 3)),
        (["U1", "U3", "U4"], 0.0),
        ([], 0.0),
    ])
    def test_reciprocal_rank(self, retrieved, expected_rr):
        assert rag_metrics.reciprocal_rank(_result("U2", retrieved)) == expected_rr


class TestAggregateMetrics:
    def test_evaluate_retrieval_empty(self):
        metrics = rag_metrics.evaluate_retrieval([])
        assert metrics == rag_metrics.RagMetrics(recall_at_k=0.0, precision_at_k=0.0, mrr=0.0, k=0, num_questions=0)

    def test_evaluate_retrieval_averages_across_questions(self):
        results = [
            _result("U2", ["U2", "U1", "U3"]),  # recall 1, precision 1/3, rr 1
            _result("U1", ["U2", "U3", "U4"]),  # recall 0, precision 0,   rr 0
        ]
        metrics = rag_metrics.evaluate_retrieval(results)

        assert metrics.num_questions == 2
        assert metrics.k == 3
        assert metrics.recall_at_k == pytest.approx(0.5)
        assert metrics.precision_at_k == pytest.approx((1 / 3) / 2)
        assert metrics.mrr == pytest.approx(0.5)

    def test_evaluate_retrieval_perfect_run(self):
        results = [_result("U2", ["U2", "U1", "U3"]), _result("U1", ["U1", "U2", "U3"])]
        metrics = rag_metrics.evaluate_retrieval(results)

        assert metrics.recall_at_k == 1.0
        assert metrics.mrr == 1.0
