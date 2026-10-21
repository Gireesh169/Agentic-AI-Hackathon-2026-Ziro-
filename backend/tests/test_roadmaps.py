from datetime import datetime, timezone
from uuid import uuid4

from app.store import Store
from app.models import GoalInput, GenerationMetadata, LearningPlan, LearningWeek, PlanGenerationResult, RoadmapSaveInput


def in_memory_store(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    return Store()


def roadmap_record(user_id: str, title: str = "Plan"):
    week_id = str(uuid4())
    return {
        "id": str(uuid4()),
        "user_id": user_id,
        "title": title,
        "career_goal": title,
        "skill_level": "Beginner",
        "weekly_hours": 5,
        "duration_weeks": 1,
        "total_estimated_hours": 5,
        "generation_mode": "fallback",
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "weeks": [{
            "id": week_id,
            "week_number": 1,
            "title": "Foundations",
            "learning_objectives": ["Complete a task"],
            "activities": ["Practice"],
            "estimated_hours": 5,
            "completion_status": "not_started",
            "resources": [{
                "id": str(uuid4()),
                "title": "Docs",
                "url": "https://example.com/docs",
                "resource_type": "documentation",
                "access_status": "unknown",
                "verification_status": "not_checked",
                "verification_evidence": None,
                "is_completed": False,
            }],
        }],
    }


def test_roadmaps_are_separate_and_owner_scoped(monkeypatch):
    store = in_memory_store(monkeypatch)
    first = store.save_roadmap("user-a", roadmap_record("user-a", "First"))
    second = store.save_roadmap("user-a", roadmap_record("user-a", "Second"))
    assert len(store.list_roadmaps("user-a")) == 2
    assert store.get_roadmap("user-a", first["id"])["title"] == "First"
    assert store.get_roadmap("user-b", first["id"]) is None
    assert store.get_roadmap("user-a", second["id"])["title"] == "Second"


def test_progress_updates_persist_in_store(monkeypatch):
    store = in_memory_store(monkeypatch)
    record = store.save_roadmap("user-a", roadmap_record("user-a"))
    week = record["weeks"][0]
    resource = week["resources"][0]
    store.update_week("user-a", record["id"], week["id"], "completed")
    store.update_resource("user-a", record["id"], resource["id"], True)
    loaded = store.get_roadmap("user-a", record["id"])
    assert loaded["weeks"][0]["completion_status"] == "completed"
    assert loaded["weeks"][0]["resources"][0]["is_completed"] is True
    assert store.list_roadmaps("user-a")[0]["progress_percent"] == 100


def test_delete_is_owner_scoped(monkeypatch):
    store = in_memory_store(monkeypatch)
    record = store.save_roadmap("user-a", roadmap_record("user-a"))
    assert not store.delete_roadmap("user-b", record["id"])
    assert store.get_roadmap("user-a", record["id"]) is not None
    assert store.delete_roadmap("user-a", record["id"])
    assert store.get_roadmap("user-a", record["id"]) is None


def test_supabase_store_uses_server_key_when_creating_client(monkeypatch):
    captured = {}

    class FakeClient:
        pass

    fake_client = FakeClient()
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "fallback-key")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "server-key")

    def create_client(url, key):
        captured["url"] = url
        captured["key"] = key
        return fake_client

    monkeypatch.setattr("supabase.create_client", create_client)

    store = Store()

    assert store.client is fake_client
    assert captured == {"url": "https://example.supabase.co", "key": "server-key"}


def test_saved_roadmap_can_provide_legacy_approval_plan_shape():
    record = roadmap_record("user-a", "Data Analyst")
    record["total_estimated_hours"] = 4
    plan = Store._legacy_plan(record)

    assert plan == {
        "title": "Data Analyst",
        "planned_hours": 4,
        "weeks": [{
            "week": 1,
            "topic": "Foundations",
            "hours": 5,
            "activities": ["Practice"],
            "outcome": "Complete a task",
        }],
    }


def test_save_payload_requires_validated_matching_horizon():
    goal = GoalInput(goal="Learn Python", level="Beginner", weekly_hours=5, duration_months=1)
    weeks = [
        LearningWeek(
            week=index,
            topic=f"Python topic {index}",
            hours=1,
            activities=["Practice"],
            outcome=f"Complete milestone {index}",
        )
        for index in range(1, 5)
    ]
    plan = LearningPlan(
        title="Learn Python",
        summary="A focused plan",
        total_available_hours=15,
        planned_hours=4,
        fits_budget=True,
        weeks=weeks,
    )
    generation = GenerationMetadata(
        generation_mode="fallback",
        generated_at=datetime.now(timezone.utc),
        validation_status="passed",
        total_estimated_hours=4,
        available_total_hours=15,
    )
    payload = RoadmapSaveInput(
        preview_id=uuid4(),
        goal=goal,
        generation=PlanGenerationResult(plan=plan, generation=generation),
    )

    assert len(payload.generation.plan.weeks) == 4
