from datetime import datetime
from uuid import UUID
from typing import Literal
from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

class GoalInput(BaseModel):
    goal: str = Field(min_length=4, max_length=240)
    level: Literal["Beginner", "Intermediate", "Advanced"]
    weekly_hours: int = Field(ge=1, le=40)
    duration_months: int = Field(ge=1, le=24)

    @field_validator("goal")
    @classmethod
    def validate_goal(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Goal must not be blank.")
        return value

class LearningWeek(BaseModel):
    week: int = Field(ge=1)
    topic: str = Field(min_length=1, max_length=240)
    hours: float = Field(gt=0, le=40)
    activities: list[str] = Field(min_length=1)
    outcome: str = Field(min_length=1, max_length=500)
    resource_queries: list[str] = Field(default_factory=list)

    @field_validator("topic")
    @classmethod
    def validate_topic(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Each week must have a meaningful learning objective.")
        return value

    @field_validator("activities", "resource_queries")
    @classmethod
    def validate_text_lists(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if value.strip()]
        return cleaned

    @field_validator("outcome")
    @classmethod
    def validate_outcome(cls, value: str) -> str:
        return value.strip()

class LearningPlan(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    summary: str = Field(min_length=1, max_length=2000)
    total_available_hours: float = Field(ge=0)
    planned_hours: float = Field(ge=0)
    fits_budget: bool
    weeks: list[LearningWeek] = Field(min_length=1)

    @field_validator("title", "summary")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Required roadmap text must not be blank.")
        return value

    @model_validator(mode="after")
    def validate_structure(self):
        week_numbers = [week.week for week in self.weeks]
        expected = list(range(1, len(self.weeks) + 1))
        if week_numbers != expected:
            raise ValueError("Weeks must be unique and sequential starting at week 1.")
        calculated = sum(week.hours for week in self.weeks)
        if abs(calculated - self.planned_hours) > 0.01:
            raise ValueError("planned_hours must equal the sum of weekly hours.")
        if self.fits_budget != (calculated <= self.total_available_hours):
            raise ValueError("fits_budget is inconsistent with the roadmap hour budget.")
        return self

class GenerationMetadata(BaseModel):
    generation_mode: Literal["ai", "fallback"]
    model: str | None = None
    generated_at: datetime
    validation_status: Literal["passed", "failed"]
    warnings: list[str] = Field(default_factory=list)
    total_estimated_hours: float = Field(ge=0)
    available_total_hours: float = Field(ge=0)

class PlanGenerationResult(BaseModel):
    plan: LearningPlan
    generation: GenerationMetadata


class ResourceSnapshot(BaseModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=500)
    url: HttpUrl
    note: str | None = None


class RoadmapSaveInput(BaseModel):
    preview_id: UUID
    goal: GoalInput
    generation: PlanGenerationResult
    resources_by_week: dict[str, list[ResourceSnapshot]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_generation_budget(self):
        if self.generation.generation.validation_status != "passed":
            raise ValueError("Only validated roadmaps can be saved.")
        if self.generation.plan.planned_hours > self.generation.plan.total_available_hours:
            raise ValueError("A roadmap over the available time budget cannot be saved.")
        expected_weeks = round(self.goal.duration_months * 52 / 12)
        if len(self.generation.plan.weeks) != expected_weeks:
            raise ValueError("Roadmap duration does not match the requested planning horizon.")
        return self


class ResourceVerifyInput(BaseModel):
    url: HttpUrl
    simulate: Literal["none", "paid", "broken"] = "none"

class ApprovalInput(BaseModel):
    approved: bool
    approved_session_keys: list[str] | None = None

class SessionPreview(BaseModel):
    session_key: str
    week: int
    title: str
    hours: float
    scheduled_for: str


class ProfileResponse(BaseModel):
    id: UUID
    display_name: str | None = None
    avatar_url: HttpUrl | None = None
    created_at: datetime
    updated_at: datetime


class RoadmapStatusUpdate(BaseModel):
    status: Literal["active", "completed", "archived"]


class CompletionUpdate(BaseModel):
    completion_status: Literal["not_started", "in_progress", "completed"]


class ResourceCompletionUpdate(BaseModel):
    is_completed: bool


class RoadmapSummary(BaseModel):
    id: UUID
    title: str
    career_goal: str
    skill_level: Literal["Beginner", "Intermediate", "Advanced"]
    weekly_hours: int
    duration_weeks: int
    total_estimated_hours: float
    generation_mode: Literal["ai", "fallback"]
    status: Literal["active", "completed", "archived"]
    progress_percent: float
    created_at: datetime
    updated_at: datetime


class RoadmapDetail(RoadmapSummary):
    weeks: list[dict]
    generation: dict
