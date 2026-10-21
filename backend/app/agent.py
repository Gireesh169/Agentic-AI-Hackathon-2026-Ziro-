import logging
import os
from datetime import datetime, timezone
from math import floor

try:
    from openai import (
        APIConnectionError,
        APIStatusError,
        APITimeoutError,
        AuthenticationError,
        OpenAI,
        RateLimitError,
    )
except ImportError:  # Allows offline tests before dependencies are installed.
    OpenAI = None
    APIConnectionError = APIStatusError = APITimeoutError = AuthenticationError = RateLimitError = Exception

from .models import (
    GenerationMetadata,
    GoalInput,
    LearningPlan,
    LearningWeek,
    PlanGenerationResult,
)

logger = logging.getLogger(__name__)

class PlanGenerationError(RuntimeError):
    """Safe error raised when neither AI nor deterministic generation succeeds."""


SYSTEM_PROMPT = """
You are the planning component of Free Learning Path Builder.
Create a realistic learning roadmap for the user's goal and starting level.
Return only data matching the supplied schema.
Order topics by prerequisites. Include practice and a final portfolio/project when relevant.
Respect the available hours. Estimate durations conservatively and do not claim guaranteed career outcomes.
Do not invent course URLs. Return resource_queries as topic descriptions only.
Every week must have a distinct, specific topic, concrete activities, and a measurable outcome.
Do not reuse generic foundation activities for unrelated weeks.
"""


def available_hours(weekly_hours: int, duration_months: int) -> tuple[int, int]:
    weeks = max(1, round(duration_months * 52 / 12))
    return weeks, weekly_hours * weeks


def validate_plan_for_goal(plan: LearningPlan, goal: GoalInput) -> LearningPlan:
    weeks, budget = available_hours(goal.weekly_hours, goal.duration_months)
    if len(plan.weeks) != weeks:
        raise ValueError(f"Expected {weeks} weekly entries; received {len(plan.weeks)}.")
    if any(week.hours > goal.weekly_hours for week in plan.weeks):
        raise ValueError("A weekly workload exceeds the user's available hours.")
    planned = float(sum(week.hours for week in plan.weeks))
    if planned > budget:
        raise ValueError("The roadmap exceeds the total available hour budget.")
    return plan.model_copy(
        update={
            "total_available_hours": float(budget),
            "planned_hours": planned,
            "fits_budget": True,
        }
    )


def fallback_plan(goal: GoalInput) -> LearningPlan:
    weeks, budget = available_hours(goal.weekly_hours, goal.duration_months)
    goal_text = goal.goal.lower()
    if "spring" in goal_text or "java backend" in goal_text:
        phases = [
            ("Java syntax and object-oriented foundations", ["Write classes, methods, and constructors", "Model a small domain with encapsulation"], "Implement a small Java domain model.", ["java", "object oriented programming"]),
            ("Java collections and exceptions", ["Use List, Map, and Set appropriately", "Handle and test checked and unchecked exceptions"], "Choose collection types and handle failures deliberately.", ["java collections", "java exceptions"]),
            ("HTTP, REST, and JSON", ["Inspect HTTP methods and status codes", "Design JSON request and response examples"], "Explain and design a REST endpoint contract.", ["http rest json"]),
            ("Spring Boot application structure", ["Create a Spring Boot application", "Configure components and application properties"], "Run a Spring Boot service and explain its structure.", ["spring boot fundamentals"]),
            ("Dependency injection and configuration", ["Define services and inject dependencies", "Separate environment configuration from code"], "Build a service with testable dependency injection.", ["spring boot dependency injection"]),
            ("REST controllers and validation", ["Implement controller endpoints", "Validate request bodies and return useful errors"], "Expose a validated REST endpoint.", ["spring boot rest controllers validation"]),
            ("Service design and exception handling", ["Move business rules into services", "Add centralized exception handling"], "Return consistent success and error responses.", ["spring boot services exception handling"]),
            ("SQL and PostgreSQL fundamentals", ["Create tables and write joins", "Practice constraints and indexes"], "Design and query a relational schema.", ["postgresql sql"]),
            ("Spring Data JPA persistence", ["Map entities and repositories", "Persist and query application data"], "Connect the API to PostgreSQL through JPA.", ["spring data jpa"]),
            ("Authentication and authorization basics", ["Compare authentication and authorization", "Protect an endpoint and test access rules"], "Explain and implement a basic protected route.", ["spring security authentication authorization"]),
            ("Testing and API documentation", ["Write unit and controller tests", "Document endpoints with examples"], "Demonstrate tested endpoints with clear API documentation.", ["spring boot testing openapi"]),
            ("Backend portfolio project", ["Combine the API, validation, and persistence layers", "Add one complete feature end to end"], "Deliver a working backend feature with tests.", ["spring boot backend project"]),
            ("Deployment and interview readiness", ["Create a deployment checklist", "Explain architecture and trade-offs"], "Present the project and a concise backend development plan.", ["java backend deployment git"]),
        ]
    elif "python" in goal_text:
        phases = [
            ("Python syntax and data types", ["Write functions using strings, numbers, and collections", "Solve short expression and control-flow exercises"], "Build a small command-line script.", ["python fundamentals"]),
            ("Functions, modules, and errors", ["Split code into modules", "Handle errors and write docstrings"], "Organize a reusable Python module.", ["python functions modules exceptions"]),
            ("Object-oriented Python", ["Define classes and methods", "Use composition for a small domain"], "Model a small application domain in Python.", ["python object oriented programming"]),
            ("Files, APIs, and JSON", ["Read and write files", "Parse JSON and call a public API safely"], "Build a script that consumes structured data.", ["python json api"]),
            ("Testing and debugging", ["Write pytest-style unit tests", "Use assertions and reproduce a bug"], "Test a Python module and fix a failing case.", ["python testing debugging"]),
            ("Web or automation fundamentals", ["Choose a focused web or automation use case", "Implement a small workflow"], "Automate one repeatable task with Python.", ["python automation"]),
            ("Project implementation", ["Plan a small project into milestones", "Implement the core feature"], "Complete a scoped Python project.", ["python project"]),
            ("Project polish and portfolio", ["Refactor and document the project", "Explain design decisions and next steps"], "Publish a readable project with usage instructions.", ["python portfolio git"]),
        ]
    elif "data analyst" in goal_text or "data analysis" in goal_text:
        phases = [
            ("Spreadsheet analysis", ["Use formulas, filters, and pivot tables", "Clean a small business dataset"], "Summarize a dataset with a reproducible spreadsheet.", ["excel data analysis"]),
            ("SQL filtering and aggregation", ["Write SELECT and WHERE queries", "Group results and calculate metrics"], "Answer business questions with SQL.", ["sql aggregation"]),
            ("SQL joins and data modeling", ["Join normalized tables", "Identify duplicate and missing records"], "Produce a reliable multi-table query.", ["sql joins relational data"]),
            ("Statistics for analysis", ["Calculate distributions and summary statistics", "Interpret variability and sampling limits"], "Explain an analysis finding with appropriate caveats.", ["statistics data analysis"]),
            ("Python for data work", ["Use Python collections and notebooks", "Load and inspect tabular data"], "Create a reproducible data exploration notebook.", ["python pandas data analysis"]),
            ("Data cleaning with pandas", ["Handle missing values and types", "Create a documented cleaning pipeline"], "Transform raw data into an analysis-ready table.", ["pandas data cleaning"]),
            ("Visualization and storytelling", ["Choose suitable chart types", "Annotate a clear analytical message"], "Build a concise visual explanation.", ["data visualization"]),
            ("Dashboard design", ["Define dashboard questions and metrics", "Assemble an interactive dashboard"], "Deliver a dashboard with documented metric definitions.", ["power bi dashboard"]),
            ("Exploratory analysis project", ["Form hypotheses", "Validate them with SQL or Python"], "Complete an exploratory analysis with evidence.", ["data analysis project"]),
            ("Communication and recommendations", ["Write an executive summary", "Connect findings to decisions"], "Present actionable recommendations from data.", ["data storytelling recommendations"]),
            ("Portfolio case study", ["Document the question, method, and limitations", "Polish charts and queries"], "Publish a complete analyst case study.", ["data analyst portfolio"]),
            ("Interview and review", ["Practice analytical questions", "Review weak areas with targeted exercises"], "Explain an end-to-end analysis confidently.", ["data analyst interview"]),
        ]
    else:
        phases = [
            (f"{goal.goal} essentials", ["List the core concepts for this goal", "Complete a small introductory exercise"], "Explain the core vocabulary and complete an introductory task.", [f"{goal.goal} fundamentals"]),
            (f"{goal.goal} core technique", ["Study one central technique", "Apply it to a constrained example"], "Apply a core technique to a concrete example.", [f"{goal.goal} core skills"]),
            (f"{goal.goal} practice and feedback", ["Complete two progressively harder exercises", "Review mistakes and record corrections"], "Demonstrate improvement using feedback.", [f"{goal.goal} practice"]),
            (f"{goal.goal} applied project", ["Define a small deliverable", "Build and review the first version"], "Produce a scoped first project version.", [f"{goal.goal} project"]),
            (f"{goal.goal} project refinement", ["Add one meaningful feature", "Test or evaluate the result"], "Improve the project using evidence.", [f"{goal.goal} applied project"]),
            (f"{goal.goal} portfolio and next steps", ["Document the work and limitations", "Create a targeted next-study list"], "Present the result and identify the next learning priorities.", [f"{goal.goal} portfolio"]),
        ]
    result = []
    used_topics = set()
    for week_number in range(1, weeks + 1):
        phase_index = min(len(phases) - 1, floor((week_number - 1) * len(phases) / weeks))
        topic, activities, outcome, queries = phases[phase_index]
        if topic in used_topics:
            cycle = week_number - phase_index
            topic = f"{topic} — deliberate practice cycle {cycle}"
            outcome = f"{outcome} Complete a new example in practice cycle {cycle}."
        used_topics.add(topic)
        result.append(
            LearningWeek(
                week=week_number,
                topic=topic,
                hours=float(goal.weekly_hours),
                activities=activities,
                outcome=outcome,
                resource_queries=queries,
            )
        )
    planned = sum(item.hours for item in result)
    return LearningPlan(
        title=f"{goal.goal}: {weeks}-week learning path",
        summary=f"Starter roadmap for a {goal.level.lower()} learner. Adjust pace after reviewing progress.",
        total_available_hours=float(budget),
        planned_hours=float(planned),
        fits_budget=planned <= budget,
        weeks=result,
    )


def _fallback_result(goal: GoalInput, warning: str) -> PlanGenerationResult:
    try:
        plan = validate_plan_for_goal(fallback_plan(goal), goal)
    except (TypeError, ValueError) as exc:
        logger.error("Fallback plan validation failed error_type=%s", type(exc).__name__)
        raise PlanGenerationError("A valid learning roadmap could not be generated.") from exc
    metadata = GenerationMetadata(
        generation_mode="fallback",
        model=None,
        generated_at=datetime.now(timezone.utc),
        validation_status="passed",
        warnings=[warning],
        total_estimated_hours=plan.planned_hours,
        available_total_hours=plan.total_available_hours,
    )
    return PlanGenerationResult(plan=plan, generation=metadata)


def generate_plan_with_metadata(goal: GoalInput) -> PlanGenerationResult:
    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or OpenAI is None:
        return _fallback_result(goal, "OpenAI is not configured; a deterministic fallback roadmap was used.")

    weeks, budget = available_hours(goal.weekly_hours, goal.duration_months)
    prompt = f"""
User goal: {goal.goal}
Starting level: {goal.level}
Weekly hours: {goal.weekly_hours}
Duration: {goal.duration_months} months (plan for {weeks} weeks)
Hard total-hour budget: {budget} hours.
Create exactly {weeks} weekly entries. Each week's hours must be positive and at most {goal.weekly_hours}.
The sum of week hours must not exceed {budget}. Use topic-specific resource_queries, not URLs.
"""
    try:
        client = OpenAI(api_key=api_key, timeout=30.0, max_retries=1)
        completion = client.chat.completions.parse(
            model=model_name,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format=LearningPlan,
        )
        parsed = completion.choices[0].message.parsed
        if parsed is None:
            raise ValueError("OpenAI returned no structured roadmap.")
        validated = validate_plan_for_goal(parsed, goal)
        metadata = GenerationMetadata(
            generation_mode="ai",
            model=model_name,
            generated_at=datetime.now(timezone.utc),
            validation_status="passed",
            total_estimated_hours=validated.planned_hours,
            available_total_hours=validated.total_available_hours,
        )
        return PlanGenerationResult(plan=validated, generation=metadata)
    except (AuthenticationError, RateLimitError, APITimeoutError, APIConnectionError, APIStatusError, ValueError) as exc:
        if isinstance(exc, AuthenticationError):
            warning = "OpenAI authentication failed; a deterministic fallback roadmap was used."
            category = "authentication"
        elif isinstance(exc, RateLimitError):
            warning = "OpenAI rate limit reached; a deterministic fallback roadmap was used."
            category = "rate_limit"
        elif isinstance(exc, (APITimeoutError, APIConnectionError)):
            warning = "OpenAI was unavailable or timed out; a deterministic fallback roadmap was used."
            category = "network"
        elif isinstance(exc, APIStatusError):
            warning = "OpenAI returned a service error; a deterministic fallback roadmap was used."
            category = "service"
        else:
            warning = "OpenAI returned an invalid roadmap; a deterministic fallback roadmap was used."
            category = "invalid_output"
        logger.warning("Plan generation fallback category=%s error_type=%s", category, type(exc).__name__)
        return _fallback_result(goal, warning)


def generate_plan(goal: GoalInput) -> LearningPlan:
    """Backward-compatible plan-only API for existing callers."""
    return generate_plan_with_metadata(goal).plan
