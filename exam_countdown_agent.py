"""T29 - Exam Countdown Planner
Microsoft Foundry + Microsoft Agent Framework

Core T29 tools:
  1. set_exam(date)
  2. allocate_topics(topics)

Extension:
  3. catch_up(missed_date)
"""

from datetime import datetime, timedelta
from typing import Annotated
import os

from pydantic import Field
from azure.identity import AzureCliCredential
from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient

# Set this environment variable before running, for example in Windows CMD:
# set FOUNDRY_PROJECT_ENDPOINT=https://<resource>.services.ai.azure.com/api/projects/<project>
PROJECT_ENDPOINT = os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
if not PROJECT_ENDPOINT:
    raise RuntimeError("Set FOUNDRY_PROJECT_ENDPOINT before running the agent.")

credential = AzureCliCredential()
client = FoundryChatClient(
    project_endpoint=PROJECT_ENDPOINT,
    model="gpt-5-mini",
    credential=credential,
)

memory = {
    "exam_date": None,
    "topics": [],
    "schedule": [],
}


def set_exam(date):
    """Save or update the exam date."""
    print(f"\n TOOL CALL: set_exam({date})")
    memory["exam_date"] = date
    result = f"Exam date saved: {date}"
    print(f" TOOL RESULT: {result}")
    return result


def allocate_topics(
    topics: Annotated[
        list[str],
        Field(description="List of study topic names, e.g. ['Java', 'OOP', 'SQL', 'Spark'].")
    ]
):
    """Spread topics over the available days and reserve exam day for final revision."""
    print(f"\n TOOL CALL: allocate_topics({topics})")

    if not memory["exam_date"]:
        result = "Please set the exam date first."
        print(f" TOOL RESULT: {result}")
        return result
    if not topics:
        result = "No topics were provided."
        print(f" TOOL RESULT: {result}")
        return result

    exam_date = datetime.strptime(memory["exam_date"], "%Y-%m-%d").date()
    today = datetime.now().date()
    days_left = (exam_date - today).days
    if days_left <= 0:
        result = "The exam date has already passed."
        print(f" TOOL RESULT: {result}")
        return result

    base_days = days_left // len(topics)
    extra_days = days_left % len(topics)
    schedule = []
    current_date = today

    for i, topic in enumerate(topics):
        topic_days = base_days + (1 if i < extra_days else 0)
        for _ in range(topic_days):
            schedule.append({"date": current_date.isoformat(), "topic": topic})
            current_date += timedelta(days=1)

    schedule.append({"date": exam_date.isoformat(), "topic": "Final revision"})
    memory["topics"] = topics
    memory["schedule"] = schedule
    print(f" TOOL RESULT: {schedule}")
    return schedule


def catch_up(missed_date):
    """Merge a missed study task into the next available study day."""
    print(f"\n TOOL CALL: catch_up({missed_date})")

    if not memory["schedule"]:
        result = "There is no study schedule to adjust."
        print(f" TOOL RESULT: {result}")
        return result

    missed_date_str = datetime.strptime(missed_date, "%Y-%m-%d").date().isoformat()
    missed_items = [
        item for item in memory["schedule"]
        if item["date"] == missed_date_str and item["topic"] != "Final revision"
    ]
    if not missed_items:
        result = f"No study task was scheduled for {missed_date}."
        print(f" TOOL RESULT: {result}")
        return result

    memory["schedule"] = [
        item for item in memory["schedule"] if item["date"] != missed_date_str
    ]
    next_days = [
        item["date"] for item in memory["schedule"]
        if item["date"] > missed_date_str and item["topic"] != "Final revision"
    ]
    if not next_days:
        result = "There are no remaining study days for catch-up."
        print(f" TOOL RESULT: {result}")
        return result

    catchup_date = min(next_days)
    for missed_item in missed_items:
        existing = next((
            item for item in memory["schedule"]
            if item["date"] == catchup_date and item["topic"] == missed_item["topic"]
        ), None)
        if existing:
            existing["topic"] += " + catch-up"
        else:
            memory["schedule"].append({
                "date": catchup_date,
                "topic": missed_item["topic"] + " (catch-up)",
            })

    memory["schedule"].sort(key=lambda x: x["date"])
    print(f" TOOL RESULT: {memory['schedule']}")
    return memory["schedule"]


agent = Agent(
    client=client,
    name="ExamCountdownPlanner",
    instructions="""
You are an Exam Countdown Planner.

Use the available tools to manage the user's exam plan.

Use set_exam when the user provides or changes an exam date.
Use allocate_topics when the user provides study topics and needs a day-by-day plan.
Use catch_up when the user reports a missed study day.

When a request contains both an exam date and study topics, call set_exam first and then allocate_topics.
After a tool returns a result, use that result to decide what to do next.
Do not invent a different schedule after a planning tool returns a schedule.
""",
    tools=[set_exam, allocate_topics, catch_up],
)


async def main():
    response = await agent.run(
        "My exam is on 2026-09-05. I need to study Java, OOP, SQL, and Spark."
    )
    print("\nFINAL AGENT RESPONSE:")
    print(response.text)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
