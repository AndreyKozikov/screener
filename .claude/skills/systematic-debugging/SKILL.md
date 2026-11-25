---
name: systematic-debugging
description: Use only to analyze a supplied stack trace/error output, or when the user asks to fix an application runtime error or a failure that occurred during testing.
---

# Systematic Debugging

Adapted from [obra/superpowers](https://github.com/obra/superpowers/tree/main/skills/systematic-debugging), distributed under the MIT License (Copyright (c) 2025 Jesse Vincent).

## Activation boundary

Use this workflow only when at least one condition is true:

- The user asks to analyze a stack trace, exception, error log, or failed-test output.
- The user asks to fix a runtime or application error.
- The user asks to fix a failure that occurred while running tests.

Do not use it for ordinary feature work, planned refactoring, code review without a reported error, documentation, or speculative error prevention. A passing test run or a general request to improve code is not an error trigger.

Do not load or invoke any other Superpowers workflow. This skill is self-contained.

## Procedure

1. **Anchor the investigation in evidence.** Use the exact error, stack trace, logs, command output, and reproduction steps supplied by the user. Separate observed facts from hypotheses. Do not invent missing output.
2. **Find the failing boundary.** Trace the failing value or call through the relevant layers. In this project, consider the boundaries between `frontend`, `backend`, `conversion_service`, and `db_repository` when the evidence points there.
3. **Compare with working behavior.** Inspect the implicated code and the closest working example, including its callers, configuration, and data contract.
4. **State a testable root-cause hypothesis.** Explain which evidence supports it. If evidence is insufficient to distinguish causes, ask for the smallest missing detail instead of guessing.
5. **Make the smallest root-cause fix** only when the user requested a fix. Avoid unrelated cleanup and refactoring.
6. **Respect verification scope.** Do not run or add tests just because this skill was activated. Do so only when the user asks for testing/verification or the task explicitly includes it. Never claim a check passed unless you ran it and inspected its result. If no verification was requested or run, say so clearly.

## Communication and code language

- Communicate with the user only in Russian.
- Write code comments and docstrings in Russian.
- In the final response, distinguish the observed error, diagnosed cause, changes made, and checks actually performed.

