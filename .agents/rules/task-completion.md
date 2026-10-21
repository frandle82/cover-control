---
trigger: always_on
---

# Task Completion

## Core rule

When Andreas gives an implementation instruction containing multiple
requirements, Codex must treat every requirement as mandatory unless it is
explicitly marked optional.

Do not stop after implementing only the first successful subset.

Do not interpret green tests as proof that the complete instruction has been
implemented.

The task is complete only when every requested point has been:

1. inspected
2. implemented or intentionally left unchanged for a proven technical reason
3. verified
4. covered by appropriate regression tests
5. checked against the final repository state

---

## Requirement checklist

At the start of implementation, derive an internal checklist from the user's
instruction.

Example:

- [ ] Room translations use the correct ConfigEntry namespace
- [ ] ConfigSubentryFlow dependency removed
- [ ] v4 migrates to v8
- [ ] v5 migrates to v8
- [ ] v6 migrates to v8
- [ ] v7 migrates to v8
- [ ] migration is idempotent
- [ ] regression tests updated
- [ ] full suite passes

Do not mark a requirement complete because adjacent code was changed.

Verify the exact requested end state.

---

## No partial completion by default

If Andreas says:

- "vollständig umsetzen"
- "arbeite weiter"
- "setze die fehlenden Punkte um"
- "arbeite die Anweisung ab"

Codex must continue until all actionable requirements are complete.

Do not stop after:

- analysis only
- one commit
- focused tests only
- fixing one of several findings
- finding additional work
- reporting that something "still needs to be done"

Instead, implement the remaining work in the same task.

---

## Evidence before completion

For every major acceptance criterion, inspect the final code after the edits.

Do not rely only on the patch that was intended.

Examples:

If the requirement says active Room translations belong in `config.step`:

verify the final translation files and tests actually use `config.step`.

If the requirement says all migrations end at v8:

verify final tests assert:

entry.version == 8

for v4, v5, v6, and v7 paths.

Search for stale assertions such as:

entry.version == 7

and classify every remaining occurrence.

If one remains intentionally, explain why.

---

## Search for stale implementation

After making changes, search repository-wide for obsolete concepts related
to the task.

Examples:

ConfigSubentryFlow
RoomSubentryFlow
config_subentries
version == 7
migrates_to_v7
_get_reconfigure_subentry

Every remaining hit must be classified as:

- active and correct
- legacy compatibility
- migration-only
- test-only
- stale and must be removed

Do not leave unexplained stale references.

---

## Tests are necessary but not sufficient

Passing tests do not prove task completion if the tests still encode the old
behavior.

Before accepting green tests:

- review the relevant assertions
- confirm they test the requested new behavior
- rename stale tests
- remove tests that protect obsolete architecture
- add regression tests for the actual bug

Example:

A translation test that asserts active Room translations exist under
`config_subentries.room.step` is wrong if the requested architecture requires
normal ConfigEntry translations under `config.step`.

Update the test instead of treating its success as evidence.

---

## Root-cause discipline

For every reported bug:

1. reproduce or identify the failing state
2. state the root-cause hypothesis
3. verify the hypothesis against code/API behavior
4. implement the smallest complete fix
5. add regression coverage
6. re-check the original symptom

Avoid shotgun edits.

---

## Migration work

For schema/version migrations, test complete user upgrade paths.

If current VERSION is N, every supported older version must end at N unless
Home Assistant explicitly guarantees and tests iterative re-entry.

Prefer testing the complete migration from each supported version.

For Cover Control v8 this means explicitly verifying:

- v4 -> v8
- v5 -> v8
- v6 -> v8
- v7 -> v8
- v8 -> v8 idempotent

Also verify:

- no duplicate Room ConfigEntries
- no stale Room ConfigSubentries
- no stale Profile ConfigSubentries
- no Profile ConfigEntries
- Registry links remain valid

---

## Translation work

Whenever ConfigFlow step structure changes:

verify all three files:

custom_components/cover_control/strings.json
custom_components/cover_control/translations/en.json
custom_components/cover_control/translations/de.json

They must remain structurally synchronized.

Verify the namespace used by the actual Home Assistant flow type.

Do not preserve an old namespace simply because an old test expects it.

---

## Completion gate

Before finalizing an implementation task, perform this gate:

1. Re-read the user's complete instruction.
2. Compare every requested point with the final code.
3. Search for stale old behavior.
4. Run focused tests.
5. Run full tests.
6. Run compileall.
7. Run translation/JSON checks.
8. Run git diff --check.
9. Run repository validation scripts.
10. Inspect git diff and git status.
11. Commit.
12. Push working branch.
13. Inspect CI when available.
14. Fix task-related CI failures.
15. Only then report completion.

If any requested item is still incomplete, continue working instead of
finalizing.

---

## Blocked work

Only stop incomplete when there is a genuine external blocker such as:

- unavailable credentials
- unavailable service
- missing required user data
- repository permission failure
- API/tool limitation that prevents the requested operation

A difficult implementation is not a blocker.

A failing test is not a reason to stop; investigate and fix it.

If blocked:

- complete every unaffected requirement first
- report the exact blocker
- provide evidence
- state precisely what remains

---

## Final report

The final report must mirror the original requirements.

For each requested point use one of:

- DONE
- NOT APPLICABLE, with reason
- BLOCKED, with exact blocker

Do not use vague wording such as:

- mostly done
- should work
- likely fixed
- appears correct

when the state can be verified.

Include:

- branch
- commit SHA
- changed files
- focused test result
- full suite result
- validation result
- CI result if available
- git status
- remaining blockers

If there are no blockers, explicitly state:

All requested implementation points are complete.