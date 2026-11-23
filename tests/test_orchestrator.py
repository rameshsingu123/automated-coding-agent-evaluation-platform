from eval_platform.models import EvaluationCase
from eval_platform.orchestrator import AdapterBinding, evaluate


class MixedAdapter:
    def run(self, case):
        if case.case_id == "raises":
            raise RuntimeError("controlled failure")
        if case.case_id == "not-string":
            return None
        return case.expected_output


def test_orchestration_preserves_declared_order_and_isolates_errors():
    cases = [
        EvaluationCase("raises", "p", "ok"),
        EvaluationCase("not-string", "p", "ok"),
        EvaluationCase("works", "p", "ok"),
    ]
    run = evaluate("experiment", cases, [AdapterBinding("adapter", MixedAdapter())], max_workers=3)

    assert [outcome.case_id for outcome in run.outcomes] == ["raises", "not-string", "works"]
    assert "RuntimeError: controlled failure" == run.outcomes[0].error
    assert "expected str" in run.outcomes[1].error
    assert run.outcomes[2].actual_output == "ok"
    assert run.scores[0].score == 1 / 3
