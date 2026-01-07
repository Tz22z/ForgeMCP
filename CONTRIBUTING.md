# Contributing

ForgeMCP favors changes that can be measured under fixed model and budget settings.

1. Create a focused branch and include tests for behavior changes.
2. Run `make quality` before opening a pull request.
3. For agent-policy changes, add a negative test showing the rejected action.
4. For context changes, report both solve quality and resource metrics; avoid tuning on
   hidden grader tests.
5. Keep tool schemas narrow and shell-free.

Commits use conventional prefixes such as `feat:`, `fix:`, `test:`, and `docs:`.

