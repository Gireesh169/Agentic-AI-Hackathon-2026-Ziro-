import os
from uuid import uuid4
from datetime import datetime, timezone
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from .auth import get_current_user
from .models import (
    ApprovalInput,
    CompletionUpdate,
    GoalInput,
    PlanGenerationResult,
    RoadmapSaveInput,
    ResourceCompletionUpdate,
    RoadmapStatusUpdate,
    ResourceVerifyInput,
)
from .agent import PlanGenerationError, generate_plan_with_metadata
from .resources import CATALOG, find_resources, verify_resource
from .store import store
from .test_cases import run_all_cases, create_test_run_record

load_dotenv()
app = FastAPI(title="Free Learning Path Builder API", version="0.1.0")

configured_origins = os.getenv("FRONTEND_ORIGINS") or os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
allowed_origins = [item.strip().rstrip("/") for item in configured_origins.split(",") if item.strip()]
if "http://127.0.0.1:5173" not in allowed_origins:
    allowed_origins.append("http://127.0.0.1:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    supabase_configured = bool(
        os.getenv("SUPABASE_URL")
        and (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SECRET_KEY"))
    )
    return {
        "status": "ok",
        "supabase": bool(store.client),
        "supabase_auth_configured": supabase_configured,
        "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
    }

def _saved_roadmap(
    user_id: str,
    goal: GoalInput,
    generation: PlanGenerationResult,
    resources_by_week: dict,
    roadmap_id: str | None = None,
) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    roadmap_id = roadmap_id or str(uuid4())
    weeks = []
    for week in generation.plan.weeks:
        week_id = str(uuid4())
        resources = []
        for resource in resources_by_week.get(str(week.week), []):
            resources.append({
                "id": str(uuid4()),
                "title": resource["title"],
                "url": str(resource["url"]),
                "resource_type": "course_or_documentation",
                "access_status": "unknown",
                "verification_status": "not_checked",
                "verification_evidence": None,
                "is_completed": False,
            })
        weeks.append({
            "id": week_id,
            "week_number": week.week,
            "title": week.topic,
            "learning_objectives": [week.outcome],
            "activities": week.activities,
            "estimated_hours": week.hours,
            "completion_status": "not_started",
            "resources": resources,
        })
    return {
        "id": roadmap_id,
        "user_id": user_id,
        "title": generation.plan.title,
        "career_goal": goal.goal,
        "skill_level": goal.level,
        "weekly_hours": goal.weekly_hours,
        "duration_weeks": len(generation.plan.weeks),
        "total_estimated_hours": generation.plan.planned_hours,
        "generation_mode": generation.generation.generation_mode,
        "generation": generation.generation.model_dump(mode="json"),
        "status": "active",
        "created_at": now,
        "updated_at": now,
        "weeks": weeks,
        "input": goal.model_dump(),
        "plan": generation.plan.model_dump(),
        "resources_by_week": {
            str(week["week_number"]): week["resources"] for week in weeks
        },
        "approval_status": "NOT_REQUESTED",
        "execution_status": "NOT_EXECUTED",
    }


@app.post("/api/plan")
def create_plan(goal: GoalInput, user: dict = Depends(get_current_user)):
    try:
        generation = generate_plan_with_metadata(goal)
    except PlanGenerationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    plan = generation.plan
    resources_by_topic = {}
    for week in plan.weeks:
        items = []
        for query in week.resource_queries or [week.topic]:
            for resource in find_resources(query, limit=2):
                if resource["id"] not in {r["id"] for r in items}:
                    items.append(resource)
        resources_by_topic[str(week.week)] = items[:3]
    return _saved_roadmap(user["id"], goal, generation, resources_by_topic)


@app.post("/api/roadmaps")
def save_generated_roadmap(payload: RoadmapSaveInput, user: dict = Depends(get_current_user)):
    existing = store.get_roadmap(user["id"], str(payload.preview_id))
    if existing:
        return existing
    try:
        record = _saved_roadmap(
            user["id"],
            payload.goal,
            payload.generation,
            {key: [resource.model_dump(mode="json") for resource in resources] for key, resources in payload.resources_by_week.items()},
            roadmap_id=str(payload.preview_id),
        )
        return store.save_roadmap(user["id"], record)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="The roadmap could not be saved. Please retry.") from exc


@app.get("/api/me")
def current_profile(user: dict = Depends(get_current_user)):
    try:
        return store.get_profile(user)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="The profile could not be loaded.") from exc


@app.get("/api/roadmaps")
def list_roadmaps(user: dict = Depends(get_current_user)):
    return store.list_roadmaps(user["id"])


@app.get("/api/roadmaps/{roadmap_id}")
def get_saved_roadmap(roadmap_id: str, user: dict = Depends(get_current_user)):
    record = store.get_roadmap(user["id"], roadmap_id)
    if not record:
        raise HTTPException(status_code=404, detail="Roadmap not found.")
    return record


@app.patch("/api/roadmaps/{roadmap_id}")
def update_saved_roadmap(roadmap_id: str, payload: RoadmapStatusUpdate, user: dict = Depends(get_current_user)):
    record = store.update_roadmap(user["id"], roadmap_id, {"status": payload.status})
    if not record:
        raise HTTPException(status_code=404, detail="Roadmap not found.")
    return record


@app.post("/api/roadmaps/{roadmap_id}/duplicate")
def duplicate_roadmap(roadmap_id: str, user: dict = Depends(get_current_user)):
    source = store.get_roadmap(user["id"], roadmap_id)
    if not source:
        raise HTTPException(status_code=404, detail="Roadmap not found.")
    copy = {**source, "id": str(uuid4()), "title": f"{source['title']} (Copy)", "status": "active"}
    copy["created_at"] = datetime.now(timezone.utc).isoformat()
    copy["updated_at"] = copy["created_at"]
    copy["weeks"] = []
    for source_week in source["weeks"]:
        week = {**source_week, "id": str(uuid4()), "completion_status": "not_started", "resources": []}
        for source_resource in source_week["resources"]:
            week["resources"].append({**source_resource, "id": str(uuid4()), "is_completed": False})
        copy["weeks"].append(week)
    return store.save_roadmap(user["id"], copy)


@app.delete("/api/roadmaps/{roadmap_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_saved_roadmap(roadmap_id: str, user: dict = Depends(get_current_user)):
    if not store.delete_roadmap(user["id"], roadmap_id):
        raise HTTPException(status_code=404, detail="Roadmap not found.")


@app.patch("/api/roadmaps/{roadmap_id}/weeks/{week_id}")
def update_saved_week(roadmap_id: str, week_id: str, payload: CompletionUpdate, user: dict = Depends(get_current_user)):
    week = store.update_week(user["id"], roadmap_id, week_id, payload.completion_status)
    if week is None:
        raise HTTPException(status_code=404, detail="Roadmap week not found.")
    return week


@app.patch("/api/roadmaps/{roadmap_id}/resources/{resource_id}")
def update_saved_resource(roadmap_id: str, resource_id: str, payload: ResourceCompletionUpdate, user: dict = Depends(get_current_user)):
    resource = store.update_resource(user["id"], roadmap_id, resource_id, payload.is_completed)
    if resource is None:
        raise HTTPException(status_code=404, detail="Roadmap resource not found.")
    return resource

@app.get("/api/plans/{plan_id}")
def get_plan(plan_id: str, user: dict = Depends(get_current_user)):
    record = store.get_roadmap(user["id"], plan_id)
    if not record:
        raise HTTPException(status_code=404, detail="Plan not found")
    return record

@app.get("/api/resources")
def get_resources(topic: str = "data analyst"):
    resources = find_resources(topic, limit=5)
    return {"topic": topic, "resources": resources}

@app.post("/api/resources/verify")
def verify(input_data: ResourceVerifyInput):
    url = str(input_data.url)
    catalog_candidate = any(item["url"] == url for item in CATALOG)
    result = verify_resource(url, simulate=input_data.simulate, catalog_candidate=catalog_candidate)
    return result

@app.post("/api/approvals/preview")
def preview_actions(payload: dict, user: dict = Depends(get_current_user)):
    plan_id = payload.get("plan_id")
    record = store.get_roadmap(user["id"], plan_id) if plan_id else None
    if not record:
        raise HTTPException(status_code=404, detail="Plan not found")
    sessions = []
    for week in record["plan"]["weeks"]:
        key = f"{plan_id}:week:{week['week']}"
        sessions.append({
            "session_key": key,
            "plan_id": plan_id,
            "week": week["week"],
            "title": week["topic"],
            "hours": week["hours"],
            "scheduled_for": f"Week {week['week']} — choose a real date/time after approval"
        })
    return {
        "plan_id": plan_id,
        "action_mode": "MOCK_ONLY",
        "warning": "Preview only. This starter does not create real calendar events or enrollments.",
        "proposed_sessions": sessions,
        "existing_sessions": store.list_sessions(plan_id)
    }

@app.post("/api/approvals/{plan_id}")
def approve_actions(plan_id: str, approval: ApprovalInput, user: dict = Depends(get_current_user)):
    record = store.get_roadmap(user["id"], plan_id)
    if not record:
        raise HTTPException(status_code=404, detail="Plan not found")
    approval_record = {
        "plan_id": plan_id,
        "approved": approval.approved,
        "approved_at": datetime.now(timezone.utc).isoformat() if approval.approved else None,
        "mode": "MOCK_ONLY",
    }
    store.save_approval(plan_id, approval_record)
    record["approval_status"] = "APPROVED" if approval.approved else "REJECTED"
    if not approval.approved:
        record["execution_status"] = "NOT_EXECUTED"
        store.update_roadmap(user["id"], plan_id, {"status": record["status"]})
        return {"approval": approval_record, "execution": {"status": "NOT_EXECUTED", "created": 0, "message": "User rejected the proposed actions."}}
    allowed_keys = set(approval.approved_session_keys or [])
    created = 0
    for week in record["plan"]["weeks"]:
        key = f"{plan_id}:week:{week['week']}"
        if allowed_keys and key not in allowed_keys:
            continue
        session = {
            "session_key": key, "plan_id": plan_id, "week": week["week"],
            "title": week["topic"], "hours": week["hours"],
            "status": "MOCK_CREATED",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        if store.add_session_if_missing(session):
            created += 1
    record["execution_status"] = "MOCK_EXECUTED"
    store.update_roadmap(user["id"], plan_id, {"status": record["status"]})
    return {
        "approval": approval_record,
        "execution": {
            "status": "MOCK_EXECUTED",
            "created": created,
            "total_existing": len(store.list_sessions(plan_id)),
            "message": "Mock sessions created after approval. No real calendar was modified."
        }
    }

@app.post("/api/test-cases/run-all")
def run_tests():
    results = run_all_cases()
    record = create_test_run_record(results)
    store.save_test_run(record)
    return record
