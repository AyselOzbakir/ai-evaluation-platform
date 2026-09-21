import pytest

from app.evaluators.llm_judge.rubric import Rubric, load_rubric


def test_valid_yaml_load_preserves_field_order(tmp_path):
    path = tmp_path / "rubric.yaml"
    path.write_text(
        """
name: generic
prompt_version: v1
pass_threshold: 0.7
criteria: Check the actual output against the expected output.
fields:
  input:
    - question
    - language
  expected:
    - answer
  actual:
    - answer
  context:
    - citations
""",
        encoding="utf-8",
    )

    rubric = load_rubric(path)

    assert rubric.name == "generic"
    assert list(rubric.fields) == ["input", "expected", "actual", "context"]
    assert rubric.fields["input"] == ["question", "language"]


def test_invalid_threshold_is_rejected():
    with pytest.raises(ValueError, match="between 0 and 1"):
        Rubric(
            name="generic",
            prompt_version="v1",
            pass_threshold=1.1,
            criteria="criteria",
        )


def test_missing_criteria_is_rejected():
    with pytest.raises(ValueError):
        Rubric(
            name="generic",
            prompt_version="v1",
            pass_threshold=0.7,
            criteria="",
        )


def test_unsupported_field_group_is_rejected():
    with pytest.raises(ValueError, match="unsupported field groups"):
        Rubric(
            name="generic",
            prompt_version="v1",
            pass_threshold=0.7,
            criteria="criteria",
            fields={"system_specific": ["value"]},
        )


def test_multi_rubric_yaml_requires_name(tmp_path):
    path = tmp_path / "rubrics.yaml"
    path.write_text(
        """
rubrics:
  - name: one
    prompt_version: v1
    pass_threshold: 0.5
    criteria: first
  - name: two
    prompt_version: v1
    pass_threshold: 0.5
    criteria: second
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="multiple rubrics"):
        load_rubric(path)
    assert load_rubric(path, name="two").name == "two"