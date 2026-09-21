from app.core.experiment import CaseResult
from app.core.models import EvaluationCase, EvaluationResult, SystemOutput
from app.integrations.langfuse.hook import LangfuseObservabilityHook


class FakeObservation:
    def __init__(self, name, metadata):
        self.name = name
        self.metadata = metadata
        self.children = []
        self.scores = []
        self.ended = False

    def start_observation(self, name, metadata, input_data=None):
        child = FakeObservation(name, metadata)
        self.children.append(child)
        return child

    def score(self, **kwargs):
        self.scores.append(kwargs)

    def end(self):
        self.ended = True


class FakeClient:
    enabled = True

    def __init__(self):
        self.observations = []
        self.flush_count = 0

    def start_observation(self, name, metadata, input_data=None):
        observation = FakeObservation(name, metadata)
        self.observations.append(observation)
        return observation

    def flush(self):
        self.flush_count += 1


def test_hook_records_case_evaluator_metadata_and_numeric_score():
    client = FakeClient()
    hook = LangfuseObservabilityHook(
        client,
        {
            "experiment_id": "exp-1",
            "system": "synthetic",
            "dataset_version": "v1",
            "application_version": "app-v1",
        },
    )
    case = EvaluationCase(id="case-1", system="synthetic", input={})
    result = CaseResult(
        case_id="case-1",
        output=SystemOutput(output={}),
        evaluations=[
            EvaluationResult(
                evaluator="quality",
                score=0.8,
                passed=True,
                reason="good",
            ),
            EvaluationResult(
                evaluator="skipped",
                score=None,
                passed=True,
                reason="skipped",
            ),
        ],
    )

    hook.on_case_evaluated(case, result.output, result)

    case_observation = client.observations[0]
    assert case_observation.metadata["case_id"] == "case-1"
    assert case_observation.children[0].metadata["evaluator"] == "quality"
    assert case_observation.children[0].scores[0]["value"] == 0.8
    assert case_observation.children[0].scores[1]["data_type"] == "BOOLEAN"
    assert len(case_observation.children[1].scores) == 1
    assert case_observation.children[1].scores[0]["data_type"] == "BOOLEAN"


def test_hook_flushes_on_completion():
    client = FakeClient()
    hook = LangfuseObservabilityHook(client, {})

    hook.on_experiment_completed(None)

    assert client.flush_count == 1


def test_hook_fail_open_on_client_exception():
    class BrokenClient(FakeClient):
        def start_observation(self, *args, **kwargs):
            raise RuntimeError("synthetic failure")

        def flush(self):
            raise RuntimeError("synthetic flush failure")

    hook = LangfuseObservabilityHook(BrokenClient(), {})
    case = EvaluationCase(id="case", system="synthetic", input={})
    result = CaseResult(case_id="case", output=None, evaluations=[])

    hook.on_case_evaluated(case, None, result)
    hook.on_experiment_completed(None)