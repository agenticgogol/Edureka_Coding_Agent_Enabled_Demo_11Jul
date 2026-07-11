"""Minimal known-working CrewAI example — 2 agents, sequential process.

Verify against current CrewAI docs before relying on this (research-first
step) — constructor args and the Process enum have changed across
versions. Install: pip install crewai.
"""
from __future__ import annotations

from crewai import Agent, Crew, Process, Task

# In a real project, wire this LLM object through llm_client.py's provider
# selection instead of hardcoding one provider here.
researcher = Agent(
    role="Researcher",
    goal="Find concise, accurate facts about the given topic",
    backstory="A meticulous research analyst who never fabricates facts.",
    verbose=True,
)

writer = Agent(
    role="Writer",
    goal="Turn research notes into a short, clear summary",
    backstory="A writer who values clarity over flourish.",
    verbose=True,
)


def build_crew(topic: str) -> Crew:
    research_task = Task(
        description=f"Research key facts about: {topic}. List 3-5 bullet points.",
        expected_output="A bullet list of 3-5 factual points.",
        agent=researcher,
    )
    write_task = Task(
        description="Write a 2-3 sentence summary from the research bullet points.",
        expected_output="A 2-3 sentence plain-language summary.",
        agent=writer,
        context=[research_task],
    )
    return Crew(
        agents=[researcher, writer],
        tasks=[research_task, write_task],
        process=Process.sequential,
        verbose=True,
    )


def run_crew(topic: str) -> str:
    """Entrypoint the backend calls."""
    crew = build_crew(topic)
    result = crew.kickoff()
    return str(result)


if __name__ == "__main__":
    print(run_crew("retrieval-augmented generation"))
