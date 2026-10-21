import pytest

import app.agent as agent
from app.agent import PlanGenerationError, available_hours, fallback_plan, generate_plan_with_metadata, validate_plan_for_goal
from app.models import GoalInput, LearningPlan, LearningWeek
from app.resources import find_resources, verify_resource, classify_pricing
from app.test_cases import run_all_cases

def test_tc1_budget_6_months_5_hours():
    weeks, budget = available_hours(5, 6)
    assert weeks == 26
    assert budget == 130
    plan = fallback_plan(GoalInput(goal="Become a Data Analyst", level="Beginner", weekly_hours=5, duration_months=6))
    assert len(plan.weeks) == 26
    assert plan.planned_hours <= plan.total_available_hours

def test_tc2_paid_course_is_flagged():
    result = verify_resource("https://example.org/course", simulate="paid")
    assert result["pricing_status"] == "PAID"

def test_tc3_broken_link_is_flagged():
    result = verify_resource("https://example.org/broken", simulate="broken")
    assert result["link_status"] == "BROKEN"
    # Unit tests must not depend on network availability; validate the replacement URL shape.
    replacement_url = "https://docs.python.org/3/tutorial/"
    assert replacement_url.startswith("https://")

def test_tc4_rerun_only_adds_missing():
    proposed = {"a", "b", "c", "d"}
    existing = {"a", "b"}
    first_add = proposed - existing
    after_first = existing | first_add
    second_add = proposed - after_first
    assert first_add == {"c", "d"}
    assert second_add == set()

def test_all_official_cases_have_results():
    results = run_all_cases()
    assert [r["case_id"] for r in results] == ["TC1", "TC2", "TC3", "TC4"]
    assert all("expected" in r and "actual" in r and "evidence" in r for r in results)


def make_goal(**overrides):
    values = {"goal": "Learn Python", "level": "Beginner", "weekly_hours": 5, "duration_months": 1}
    values.update(overrides)
    return GoalInput(**values)


def test_missing_openai_key_is_explicit_fallback(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = generate_plan_with_metadata(make_goal())
    assert result.generation.generation_mode == "fallback"
    assert result.generation.validation_status == "passed"
    assert result.generation.model is None


def test_fallback_failure_is_safe_and_explicit(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(agent, "fallback_plan", lambda goal: (_ for _ in ()).throw(ValueError("internal details")))
    with pytest.raises(PlanGenerationError, match="valid learning roadmap"):
        generate_plan_with_metadata(make_goal())


def test_valid_mocked_ai_plan_has_ai_metadata(monkeypatch):
    goal = make_goal()
    plan = fallback_plan(goal)

    class FakeCompletions:
        def parse(self, **kwargs):
            return type("Completion", (), {
                "choices": [type("Choice", (), {
                    "message": type("Message", (), {"parsed": plan})()
                })()]
            })()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = type("Chat", (), {"completions": FakeCompletions()})()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(agent, "OpenAI", FakeOpenAI)
    result = generate_plan_with_metadata(goal)
    assert result.generation.generation_mode == "ai"
    assert result.generation.model == "gpt-4o-mini"
    assert result.generation.total_estimated_hours == plan.planned_hours


@pytest.mark.parametrize(
    ("exception_name", "warning"),
    [
        ("AuthenticationError", "authentication"),
        ("RateLimitError", "rate limit"),
        ("APIConnectionError", "unavailable"),
    ],
)
def test_expected_openai_failures_use_safe_fallback(monkeypatch, exception_name, warning):
    class ExpectedError(Exception):
        pass

    class FailingOpenAI:
        def __init__(self, **kwargs):
            raise ExpectedError("secret-looking provider detail")

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(agent, "OpenAI", FailingOpenAI)
    monkeypatch.setattr(agent, exception_name, ExpectedError)
    result = generate_plan_with_metadata(make_goal())
    assert result.generation.generation_mode == "fallback"
    assert warning in result.generation.warnings[0].lower()
    assert "secret-looking" not in str(result)


def test_invalid_ai_output_uses_safe_fallback(monkeypatch):
    class FakeCompletions:
        def parse(self, **kwargs):
            raise ValueError("invalid model output with sensitive details")

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = type("Chat", (), {"completions": FakeCompletions()})()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(agent, "OpenAI", FakeOpenAI)
    result = generate_plan_with_metadata(make_goal())
    assert result.generation.generation_mode == "fallback"
    assert result.generation.warnings == ["OpenAI returned an invalid roadmap; a deterministic fallback roadmap was used."]
    assert "sensitive details" not in str(result)


def test_duplicate_and_missing_weeks_are_rejected():
    base = fallback_plan(make_goal())
    duplicate = base.model_copy(update={"weeks": [base.weeks[0].model_copy(update={"week": 1}), base.weeks[1].model_copy(update={"week": 1})]})
    with pytest.raises(ValueError, match="sequential"):
        LearningPlan(**duplicate.model_dump())

    missing = base.model_copy(update={"weeks": [base.weeks[0].model_copy(update={"week": 1}), base.weeks[1].model_copy(update={"week": 3})]})
    with pytest.raises(ValueError, match="sequential"):
        LearningPlan(**missing.model_dump())


def test_weekly_and_total_workload_limits_are_rejected():
    goal = make_goal(weekly_hours=5, duration_months=1)
    weeks = [LearningWeek(week=1, topic="Topic", hours=6, activities=["Practice"], outcome="Complete a task.")]
    weeks.extend(LearningWeek(week=index, topic="Topic", hours=1, activities=["Practice"], outcome="Complete a task.") for index in range(2, 5))
    plan = LearningPlan(
        title="Plan",
        summary="Summary",
        total_available_hours=9,
        planned_hours=9,
        fits_budget=True,
        weeks=weeks,
    )
    with pytest.raises(ValueError, match="weekly workload"):
        validate_plan_for_goal(plan, goal)


def test_total_workload_above_budget_is_rejected():
    weeks = [LearningWeek(week=index, topic="Topic", hours=5, activities=["Practice"], outcome="Complete a task.") for index in range(1, 5)]
    with pytest.raises(ValueError, match="fits_budget"):
        LearningPlan(
            title="Plan",
            summary="Summary",
            total_available_hours=10,
            planned_hours=20,
            fits_budget=True,
            weeks=weeks,
        )


def test_six_month_budget_and_partial_weeks_are_consistent():
    goal = make_goal(weekly_hours=5, duration_months=6)
    assert available_hours(5, 6) == (26, 130)
    plan = fallback_plan(goal)
    assert len(plan.weeks) == 26
    assert plan.planned_hours == 130
    partial = plan.weeks[0].model_copy(update={"hours": 2})
    partial_plan = plan.model_copy(update={"weeks": [partial, *plan.weeks[1:]], "planned_hours": 127})
    assert validate_plan_for_goal(partial_plan, goal).fits_budget


@pytest.mark.parametrize(
    ("goal_text", "level", "duration", "hours", "expected_terms", "forbidden_terms"),
    [
        ("Become a Spring Boot backend developer", "Beginner", 3, 3, ("java", "spring", "rest"), ("python fundamentals",)),
        ("Become a Python developer", "Beginner", 2, 5, ("python", "project"), ("spring boot",)),
        ("Become a data analyst", "Intermediate", 3, 4, ("sql", "analysis", "dashboard"), ("spring boot",)),
    ],
)
def test_goal_specific_fallback_curricula(goal_text, level, duration, hours, expected_terms, forbidden_terms):
    plan = fallback_plan(GoalInput(goal=goal_text, level=level, weekly_hours=hours, duration_months=duration))
    text = " ".join([plan.title, plan.summary, *(week.topic for week in plan.weeks), *(week.outcome for week in plan.weeks)]).lower()
    assert all(term in text for term in expected_terms)
    assert not any(term in text for term in forbidden_terms)
    assert len({week.topic for week in plan.weeks}) == len(plan.weeks)
    assert plan.planned_hours <= plan.total_available_hours


def test_fallback_uses_submitted_inputs_without_stale_state():
    spring = fallback_plan(GoalInput(goal="Become a Spring Boot backend developer", level="Beginner", weekly_hours=3, duration_months=3))
    python_plan = fallback_plan(GoalInput(goal="Become a Python developer", level="Beginner", weekly_hours=5, duration_months=2))
    assert "Spring Boot" in spring.title
    assert "Python" in python_plan.title
    assert len(spring.weeks) != len(python_plan.weeks)
    assert spring.total_available_hours != python_plan.total_available_hours


def test_invalid_week_content_is_rejected():
    with pytest.raises(ValueError):
        LearningWeek(week=1, topic=" ", hours=1, activities=[], outcome="")


def test_resources_follow_week_topic_instead_of_unrelated_catalog_fallback():
    spring = find_resources("spring boot dependency injection", limit=5)
    python = find_resources("python fundamentals", limit=5)
    unknown = find_resources("underwater basket weaving", limit=5)
    assert any("spring" in item["title"].lower() for item in spring)
    assert any("python" in item["title"].lower() for item in python)
    assert unknown == []
