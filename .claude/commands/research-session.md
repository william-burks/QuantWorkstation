# Research Session Protocol

Spawn the research-navigator agent.

Pass the user's message (or empty string if none) as the agent prompt.
The research-navigator agent owns all phases: session start (graph screening + shortlist), redundancy check, pivot analysis, and session wrap.

Do not re-implement phases here. The agent definition is the source of truth.
