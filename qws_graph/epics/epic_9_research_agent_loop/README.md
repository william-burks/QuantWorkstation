# Epic 9 — Research Agent Loop

## Objective
Close the split-brain gap. Agents navigate graph state and execute trials in a unified
research session. Will runs one command, approves direction, trial-engineer executes,
results ingest, session closes with structured report.

## Entry Criteria
Epic 7 COMPLETE — FormerChampion lifecycle (QWS-0801), OpenAI curation (QWS-0703), and
Pre-Graph Ideation Layer (QWS-0704) all merged to main.

## Exit Criteria
Will can run `/research-session`, receive a structured brief, approve a direction, have
trial-engineer execute + ingest, and receive a summary report — all in one session.

## Stories

| ID | Story | Status | Blocked On |
|---|---|---|---|
| QWS-0901 | Research Ideas Layer | DRAFT | — |
| QWS-0902 | Research Navigator Agent | DRAFT | Epic 7 COMPLETE |
| QWS-0903 | Trial Engineer Agent | DRAFT | QWS-0902 CLOSED |
| QWS-0904 | Research Session Command Rewrite | DRAFT | QWS-0902 + QWS-0903 CLOSED |

## Dependency Order
QWS-0901 independent — implement first or parallel with Epic 7 close.
QWS-0902 → QWS-0903 → QWS-0904 (serial chain after Epic 7).
