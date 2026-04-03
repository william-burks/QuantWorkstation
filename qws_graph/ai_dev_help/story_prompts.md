Implement #file:'qws_graph/epics/epic_1_ingestion_and_index/story_0_infra_scaffold_and_docker.md'

Instructions:
- Treat the story file as the implementation contract.
- Read any referenced docs it depends on.
- Stay within scope.
- Satisfy all acceptance criteria.
- Do not reopen architecture unless a hard repo conflict exists.
- After coding, report:
  - files changed,
  - assumptions made,
  - acceptance-criteria status,
  - and a suggested git commit message.

Commit message requirement:
- Include the commit message inline in the chat at the end of your response.
- Use a concise conventional-commit style message.
- Format it exactly like this:

Suggested commit message:
<type>(<scope>): <summary>

Optional body:
- <bullet 1>
- <bullet 2>
- <bullet 3>

Story status update requirement:
- If and only if all Story [N] acceptance criteria are satisfied, update the story file status to `CLOSED`.
- If any acceptance criterion is not satisfied, do not mark it `CLOSED`; instead leave the status as-is and list the remaining gaps explicitly.

Additional implementation constraints:
- Do not create code outside Story 0 scope unless it is the minimum required to make the entrypoint or config valid.
- If a referenced module does not exist yet, create only the thinnest viable scaffold.
- Prefer repo-native patterns over introducing new abstractions.

Please proceed with the implementation now.