# External AI Takeover Package (2026-07-22)

## Goal
Allow another AI to take over the project without relying on the long chat history or consuming unnecessary context.

## Added Files
- `AI_TAKEOVER.md`: short entry point, current baseline, read order, safety rules, commands, and user instructions.
- `.agent/prompts/MAIN_AGENT_PROMPT.md`: complete copy-paste prompt for a replacement main Agent.
- `.agent/prompts/WORKBUDDY_TASK_PROMPT.md`: copy-paste bounded Worker prompt with explicit write scope and result format.

## Verification
- Files decode as UTF-8 and contain the expected Chinese headings.
- `git diff --check` passed for the new documents.
- Control-plane unit tests passed.
- `scripts/agent_status.py .agent/tasks` still fails on the pre-existing `.agent/tasks/done/TASK-023-result.md`, which is a result report without task front matter. It was not modified.

## Next Action
Copy `.agent/prompts/MAIN_AGENT_PROMPT.md` into the new main AI. For WorkBuddy, copy `.agent/prompts/WORKBUDDY_TASK_PROMPT.md` and fill only one bounded task at a time.
