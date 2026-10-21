import os
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any
from dotenv import load_dotenv

load_dotenv()

class Store:
    """Tiny persistence adapter. Uses Supabase when configured; otherwise local memory."""
    def __init__(self):
        self.plans: dict[str, dict[str, Any]] = {}
        self.approvals: dict[str, dict[str, Any]] = {}
        self.sessions: dict[str, dict[str, Any]] = {}
        self.test_runs: list[dict[str, Any]] = []
        self.profiles: dict[str, dict[str, Any]] = {}
        self.roadmaps: dict[str, dict[str, Any]] = {}
        self.client = None
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SECRET_KEY")
        if url and key:
            try:
                from supabase import create_client
                self.client = create_client(url, key)
            except Exception as exc:
                print(f"Supabase unavailable; using in-memory storage: {exc}")

    def save_roadmap(self, user_id: str, record: dict[str, Any]) -> dict[str, Any]:
        roadmap_id = record["id"]
        self.roadmaps[roadmap_id] = record
        if self.client:
            try:
                self.client.table("roadmaps").insert({
                    "id": roadmap_id,
                    "user_id": user_id,
                    "title": record["title"],
                    "career_goal": record["career_goal"],
                    "skill_level": record["skill_level"],
                    "weekly_hours": record["weekly_hours"],
                    "duration_weeks": record["duration_weeks"],
                    "total_estimated_hours": record["total_estimated_hours"],
                    "generation_mode": record["generation_mode"],
                    "status": record["status"],
                }).execute()
                for week in record["weeks"]:
                    week_id = week["id"]
                    self.client.table("roadmap_weeks").insert({
                        "id": week_id,
                        "roadmap_id": roadmap_id,
                        "week_number": week["week_number"],
                        "title": week["title"],
                        "learning_objectives": week["learning_objectives"],
                        "activities": week["activities"],
                        "estimated_hours": week["estimated_hours"],
                        "completion_status": week["completion_status"],
                    }).execute()
                    for resource in week["resources"]:
                        self.client.table("roadmap_resources").insert({
                            "id": resource["id"],
                            "roadmap_week_id": week_id,
                            "title": resource["title"],
                            "url": resource["url"],
                            "resource_type": resource["resource_type"],
                            "access_status": resource["access_status"],
                            "verification_status": resource["verification_status"],
                            "verification_evidence": resource["verification_evidence"],
                            "is_completed": resource["is_completed"],
                        }).execute()
            except Exception:
                self.roadmaps.pop(roadmap_id, None)
                raise
        return record

    def get_profile(self, user: dict[str, Any]) -> dict[str, Any]:
        user_id = user["id"]
        if user_id not in self.profiles:
            now = datetime.now(timezone.utc).isoformat()
            self.profiles[user_id] = {
                "id": user_id,
                "display_name": user.get("user_metadata", {}).get("full_name") or user.get("email"),
                "avatar_url": user.get("user_metadata", {}).get("avatar_url"),
                "created_at": now,
                "updated_at": now,
            }
            if self.client:
                self.client.table("profiles").upsert(self.profiles[user_id]).execute()
        return self.profiles[user_id]

    def list_roadmaps(self, user_id: str) -> list[dict[str, Any]]:
        local = [r for r in self.roadmaps.values() if r["user_id"] == user_id]
        if local or not self.client:
            return sorted([self._summary(r) for r in local], key=lambda item: item["updated_at"], reverse=True)
        result = self.client.table("roadmaps").select("*").eq("user_id", user_id).order("updated_at", desc=True).execute()
        return [self._summary(r) for r in (result.data or [])]

    @staticmethod
    def _summary(record: dict[str, Any]) -> dict[str, Any]:
        weeks = record.get("weeks", [])
        total = len(weeks)
        completed = sum(week.get("completion_status") == "completed" for week in weeks)
        return {**record, "progress_percent": round((completed / total) * 100, 1) if total else 0}

    @staticmethod
    def _legacy_plan(record: dict[str, Any]) -> dict[str, Any]:
        """Expose the legacy plan shape for approval routes and older clients."""
        return {
            "title": record["title"],
            "planned_hours": record["total_estimated_hours"],
            "weeks": [
                {
                    "week": week["week_number"],
                    "topic": week["title"],
                    "hours": week["estimated_hours"],
                    "activities": week.get("activities", []),
                    "outcome": (week.get("learning_objectives") or [""])[0],
                }
                for week in record.get("weeks", [])
            ],
        }

    def get_roadmap(self, user_id: str, roadmap_id: str) -> dict[str, Any] | None:
        record = self.roadmaps.get(roadmap_id)
        if record:
            return record if record["user_id"] == user_id else None
        if not self.client:
            return None
        result = self.client.table("roadmaps").select("*").eq("id", roadmap_id).eq("user_id", user_id).limit(1).execute()
        if not result.data:
            return None
        record = result.data[0]
        weeks = self.client.table("roadmap_weeks").select("*").eq("roadmap_id", roadmap_id).order("week_number").execute()
        for week in weeks.data or []:
            resources = self.client.table("roadmap_resources").select("*").eq("roadmap_week_id", week["id"]).execute()
            week["resources"] = resources.data or []
        record["weeks"] = weeks.data or []
        record["generation"] = {}
        record["plan"] = self._legacy_plan(record)
        self.roadmaps[roadmap_id] = record
        return record

    def update_roadmap(self, user_id: str, roadmap_id: str, changes: dict[str, Any]) -> dict[str, Any] | None:
        record = self.get_roadmap(user_id, roadmap_id)
        if not record:
            return None
        record.update(changes)
        record["updated_at"] = datetime.now(timezone.utc).isoformat()
        if self.client:
            self.client.table("roadmaps").update({"status": record["status"], "updated_at": record["updated_at"]}).eq("id", roadmap_id).eq("user_id", user_id).execute()
        return record

    def update_week(self, user_id: str, roadmap_id: str, week_id: str, status: str) -> dict[str, Any] | None:
        record = self.get_roadmap(user_id, roadmap_id)
        if not record:
            return None
        for week in record["weeks"]:
            if week["id"] == week_id:
                week["completion_status"] = status
                if self.client:
                    self.client.table("roadmap_weeks").update({"completion_status": status}).eq("id", week_id).eq("roadmap_id", roadmap_id).execute()
                record["updated_at"] = datetime.now(timezone.utc).isoformat()
                return week
        return None

    def update_resource(self, user_id: str, roadmap_id: str, resource_id: str, completed: bool) -> dict[str, Any] | None:
        record = self.get_roadmap(user_id, roadmap_id)
        if not record:
            return None
        for week in record["weeks"]:
            for resource in week["resources"]:
                if resource["id"] == resource_id:
                    resource["is_completed"] = completed
                    if self.client:
                        self.client.table("roadmap_resources").update({"is_completed": completed}).eq("id", resource_id).eq("roadmap_week_id", week["id"]).execute()
                    record["updated_at"] = datetime.now(timezone.utc).isoformat()
                    return resource
        return None

    def delete_roadmap(self, user_id: str, roadmap_id: str) -> bool:
        record = self.get_roadmap(user_id, roadmap_id)
        if not record:
            return False
        if self.client:
            self.client.table("roadmaps").delete().eq("id", roadmap_id).eq("user_id", user_id).execute()
        self.roadmaps.pop(roadmap_id, None)
        return True

    def save_plan(self, plan_id: str, record: dict[str, Any]):
        self.plans[plan_id] = record
        if self.client:
            try:
                self.client.table("learning_plans").upsert(
                    {"id": plan_id, "data": record}
                ).execute()
            except Exception as exc:
                print(f"Supabase plan save failed: {exc}")

    def get_plan(self, plan_id: str):
        if plan_id in self.plans:
            return self.plans[plan_id]
        if self.client:
            try:
                result = self.client.table("learning_plans").select("data").eq("id", plan_id).limit(1).execute()
                if result.data:
                    self.plans[plan_id] = result.data[0]["data"]
                    return self.plans[plan_id]
            except Exception as exc:
                print(f"Supabase plan read failed: {exc}")
        return None

    def save_approval(self, plan_id: str, record: dict[str, Any]):
        self.approvals[plan_id] = record
        if self.client:
            try:
                self.client.table("approvals").upsert(
                    {"plan_id": plan_id, "data": record}
                ).execute()
            except Exception as exc:
                print(f"Supabase approval save failed: {exc}")

    def add_session_if_missing(self, session: dict[str, Any]) -> bool:
        key = session["session_key"]
        if key in self.sessions:
            return False
        if self.client:
            try:
                existing = (self.client.table("scheduled_sessions")
                    .select("session_key").eq("session_key", key).limit(1).execute())
                if existing.data:
                    self.sessions[key] = session
                    return False
                self.client.table("scheduled_sessions").insert(
                    {"session_key": key, "plan_id": session["plan_id"], "data": session}
                ).execute()
            except Exception as exc:
                # A unique DB constraint is the final guard if concurrent retries race.
                print(f"Supabase session write failed: {exc}")
                # Do not claim the persistent action succeeded when the write failed.
                return False
        self.sessions[key] = session
        return True

    def list_sessions(self, plan_id: str):
        local = [s for s in self.sessions.values() if s["plan_id"] == plan_id]
        if local or not self.client:
            return local
        try:
            result = self.client.table("scheduled_sessions").select("data").eq("plan_id", plan_id).execute()
            return [row["data"] for row in result.data]
        except Exception as exc:
            print(f"Supabase session read failed: {exc}")
            return local

    def save_test_run(self, record: dict[str, Any]):
        self.test_runs.append(record)
        if self.client:
            try:
                self.client.table("test_runs").insert({"id": record["id"], "data": record}).execute()
            except Exception as exc:
                print(f"Supabase test run save failed: {exc}")

store = Store()
