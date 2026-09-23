# Platform upgrade continuity

For requests to continue or upgrade this platform:

1. Read `docs/project/roadmap.md` and the current overview/latest entries in `docs/project/progress-log.md` before selecting work. The roadmap is the active long-term sequence; `roadmap-v2-history.md` is historical only.
2. Continue the current milestone's unmet acceptance gates. Once it is accepted, advance to the next planned milestone. Do not replace the main milestone with an unrelated small improvement or wait for the user to invent the next task.
3. Use the user's recorded tooling/configuration automation and BSW integration objectives to choose tradeoffs. Keep platform implementation evidence separate from the user's demonstrated learning proficiency. Do not copy personal background into public documents beyond what is needed for project planning.
4. Preserve existing user changes. Complete implementation, relevant tests, scenario evidence and progress updates. Within the current session's authorization, complete commit/push and remote CI follow-through; if blocked, record the actual permission, credentials or environment failure and the recovery step. Never describe local success as remote acceptance.
5. Record the implementation commit, actual CI run and required job conclusions before marking remote acceptance. Distinguish implementation validation from subsequent documentation-only status commits. Update the overview and the next task together.
6. Small report/usability changes belong to the active milestone's supporting work; milestone numbers represent user capabilities, not individual patches. Keep one main implementation milestone active and preserve old contract compatibility or explicitly version changes.
7. Do not send messages, open external issues, or publish contributions to other projects without the user's authorization. Commercial/physical ECU claims require actual evidence.
