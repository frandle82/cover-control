# Cover Control

Home Assistant custom integration for automated cover positioning. Runtime code
lives in `custom_components/cover_control/`; regression tests live in `tests/`;
maintenance and release scripts live in `scripts/`.

## Working rules

- Preserve unrelated user changes in the working tree.
- Keep Home Assistant callbacks non-blocking. Use `async_` APIs and schedule or
  await I/O through Home Assistant's helpers.
- Put shared constants and defaults in `const.py`; keep the public controller
  imports stable through `controller.py`.
- Runtime behavior is split into focused mixins under
  `custom_components/cover_control/runtime/`. Add logic to the owning mixin
  instead of growing the facade:
  - `actuator.py`: Cover movement commands, position tolerance, slatted blind
    tilt, and delay handling.
  - `evaluation.py`: Target position calculation and condition evaluation.
  - `events.py`: Home Assistant state listeners and event subscriptions.
  - `schedule.py`: Time schedules, workday sensors, and calendar events.
  - `shading.py`: Solar azimuth/elevation, weather conditions, and shading rules.
  - `status.py`: Active control entity state, diagnostic sensors, and status
    reasons.
- Keep `strings.json`, `translations/en.json`, and `translations/de.json` in
  sync whenever user-facing text changes.
- Maintain behavior parity with the Cover Control Automation (CCA) blueprint
  where applicable; regression tests reside in `tests/test_blueprint_parity.py`.
- Write or update the regression test alongside the implementation. A behavior
  change is incomplete until the corresponding regression test covers both the
  intended behavior and at least one relevant negative or edge case.
- Do not weaken, remove, or bypass existing regression tests merely to make a
  new implementation pass. If a behavior change intentionally alters an
  existing expectation, update the test with a clear reason and preserve
  coverage of the old edge case where applicable.

## Implementation workflow

- Inspect the relevant implementation, tests, constants, translations, and
  existing helpers before editing.
- Reuse existing patterns instead of creating parallel implementations.
- Prefer extending, simplifying, or consolidating an existing code path over
  introducing a second mechanism for the same behavior.
- Before adding a new helper, search for an existing helper or runtime method
  that already provides the required behavior.
- Follow the existing repository architecture and conventions before
  introducing a new abstraction or an external best-practice pattern.
- Keep changes scoped to the user's request. Do not perform unrelated cleanup,
  renaming, architectural refactoring, dependency updates, or formatting
  changes unless they are required for the requested behavior.
- Small refactors are acceptable when they directly reduce duplication or are
  necessary to implement the requested change safely.
- Do not move behavior between runtime mixins without a clear architectural
  reason.
- Prefer explicit and readable control flow over clever abstractions.
- Avoid speculative abstractions for behavior that is currently used only once.

## Source of truth

Keep one source of truth for each kind of state or configuration.

- Shared constants and default values belong in `const.py`.
- Persistent user configuration belongs in the Home Assistant config entry.
- Runtime-only state should remain runtime-only unless persistence is required
  for correct behavior across reloads or restarts.
- Reuse existing persisted status structures before adding new storage.
- Do not create multiple persisted configuration keys for the same logical
  setting unless separate states are intentionally exposed to the user.
- Do not copy default values into multiple runtime modules when they can be
  imported from `const.py`.
- Do not maintain parallel implementations for Config Flow and Options Flow
  when a shared helper can safely provide the same normalization or validation.
- Runtime code should consume resolved configuration rather than reinterpreting
  user input independently in multiple places.

## Configuration changes

- Avoid storing multiple configuration keys that represent the same logical
  setting.
- New user-facing options must have:
  - one canonical config key;
  - one central default;
  - matching Config Flow and Options Flow handling;
  - matching runtime handling;
  - synchronized translations;
  - regression coverage.
- If a setting is optional, prefer absence or `None` over maintaining an
  additional `use_*` flag unless the distinction is semantically necessary.
- Removing or renaming an existing persisted option requires a ConfigEntry
  migration or explicit backward-compatible normalization.
- Do not silently drop legacy configuration.
- When migrating configuration:
  - preserve existing user behavior where possible;
  - migrate old values into the canonical replacement;
  - remove obsolete keys after successful migration;
  - add regression tests for old and new config representations.
- Increase Config Flow or storage versions only when a real persisted schema
  change requires it.
- Do not invent migration logic for data that is not persisted.
- When a field is no longer supported, migrate or deliberately discard it with
  documented behavior rather than leaving dead compatibility fallbacks in the
  runtime indefinitely.

## Home Assistant integration rules

- Use Home Assistant entity, dispatcher, event, storage, and service helpers
  instead of bypassing Home Assistant internals.
- Do not access Home Assistant's database directly.
- Do not perform blocking network, filesystem, or CPU-heavy work in the event
  loop.
- Use `async_add_executor_job`, import executor helpers, or appropriate Home
  Assistant APIs when blocking work cannot be avoided.
- Entity state listeners must be removed during unload.
- Background tasks must be owned by the config entry or otherwise cleaned up
  during unload.
- Avoid unbounded background tasks or repeated polling when state listeners can
  provide the same behavior.
- Do not assume an entity exists merely because an entity ID is configured.
  Handle unavailable or missing entities safely.
- Preserve Home Assistant startup even when an optional dependency, entity, or
  diagnostic feature is unavailable.
- Use local Home Assistant time for user-visible schedules and daily state;
  use UTC where appropriate for stored timestamps and internal comparisons.
- Respect Home Assistant entity registry and device registry conventions.

## Runtime state

- Keep persisted state minimal.
- Persist only information required to preserve correct behavior across reloads
  or restarts.
- Temporary evaluation state, debounce state, pending conditions, and
  deduplication state should normally remain in memory.
- Reuse existing per-cover status structures where possible.
- Keep multi-cover behavior per cover unless an action is explicitly defined as
  group-wide.
- Do not accidentally promote a per-cover state change to every cover in the
  config entry.
- When adding state fields, ensure old stored state can still be normalized and
  loaded safely.
- Increment `STORAGE_VERSION` only if the persisted schema actually requires a
  migration.

## Cover movement rules

- All automatic movement decisions must flow through the existing controller
  and actuator paths.
- Do not call cover services from unrelated modules if an existing actuator
  method performs the same action.
- Preserve manual override, ventilation, shading, resident, lockout, and force
  priority semantics when adding new automatic behavior.
- Avoid generating duplicate cover commands when the current or target
  position is already within configured tolerance.
- Intermediate states such as `opening` and `closing` must not be interpreted
  as manual movement without considering whether Cover Control initiated the
  movement.
- Multi-cover commands must preserve any existing independent-control behavior
  for covers affected by ventilation, lockout, or manual override.

## Shading rules

- Keep solar geometry and shading-specific sensor evaluation in `shading.py`.
- Keep final action selection and target evaluation in `evaluation.py`.
- Reuse the existing configured AND/OR condition semantics instead of creating
  independent condition paths.
- Hysteresis and waiting-time logic must be stateful where required and must
  reset when the corresponding condition becomes invalid.
- Avoid duplicating the same temperature, forecast, or solar calculation for
  start and end behavior; extract a shared helper when the semantics are the
  same.
- Preserve explicit immediate-end or safety behavior when adding delayed
  shading logic.

## Manual control rules

- Distinguish between:
  - manual movement detection;
  - manual override state;
  - scheduled action history;
  - force actions.
- Do not combine these concepts into one state flag.
- A movement initiated by Cover Control must not later be interpreted as a
  manual user action.
- Manual state detection must account for devices that report intermediate
  positions during `opening` or `closing`.
- Reuse existing per-cover action history when a new feature needs to record
  that an open or close event already occurred.

## Diagnostics and logging

- Use normal Python logging for developer diagnostics.
- Use Home Assistant events, entities, or logbook mechanisms for user-facing
  diagnostics where appropriate.
- Do not emit repetitive log or logbook messages on every evaluation cycle.
- Deduplicate repeated identical runtime diagnostics when frequent state
  reevaluation could otherwise create noise.
- Optional diagnostics must never prevent the core cover automation from
  loading or running.
- Avoid exposing internal implementation details in user-facing messages unless
  they help diagnose configuration problems.

## Translations and UI

- Keep `strings.json`, `translations/en.json`, and `translations/de.json`
  structurally synchronized.
- Do not add user-facing text only in Python when Home Assistant translation
  support is available.
- Prefer translation keys for selector options over hard-coded English labels.
- Keep Config Flow and Options Flow terminology consistent.
- Reuse existing sections and menus when a new option fits naturally; do not
  create a separate menu page for one minor checkbox.
- Avoid exposing deprecated or compatibility-only settings in the current UI.
- UI labels should describe behavior rather than internal variable names.

## Tests

- Add or update regression coverage for every behavior change.
- Test both the expected behavior and a relevant negative or edge case.
- Prefer focused unit tests over broad timing-dependent integration tests when
  the behavior can be isolated.
- Avoid real network access in tests.
- Tests must not depend on the live CCA repository.
- When maintaining CCA parity, encode the relevant expected behavior locally in
  `tests/test_blueprint_parity.py`.
- Use Home Assistant test helpers and fixtures where practical.
- Keep tests deterministic.
- Prefer explicit simulated timestamps over real waiting or `asyncio.sleep`
  where time can be controlled.
- Do not reduce assertions merely to make a failing test pass.
- When fixing a bug, add a regression test that fails before the fix whenever
  practical.

## Verification

Use an isolated virtual environment (e.g. `python3 -m venv .venv` or `uv venv`)
and install `pytest-homeassistant-custom-component==0.13.365`.

During development, run the smallest relevant test set first.

For example:

```sh
python -m pytest -q tests/test_config_flow.py --asyncio-mode=auto
python -m pytest -q tests/test_blueprint_parity.py --asyncio-mode=auto
```

After focused tests pass, run the full verification suite:

```sh
python -m pytest -q --asyncio-mode=auto
python -m compileall -q custom_components tests scripts
git diff --check
```

Before every commit, inspect:

```sh
git status
git diff
git diff --check
```

Before considering a task complete, inspect the complete branch diff:

```sh
git diff origin/main...HEAD
```

Check that the diff contains only changes required for the task.

When changing release tooling, manifest versions, or packaging, also verify:

```sh
python scripts/verify_release.py --skip-tag
python scripts/build_release.py
python scripts/verify_release.py --archive --skip-tag
rm -f cover_control.zip
```

Validate commit messages before opening or updating a pull request:

```sh
python scripts/validate_commit.py --range origin/main..HEAD
```

Do not claim tests passed unless the command was actually run. If dependencies
are unavailable, report that limitation explicitly.

## Development

- Develop on a focused feature branch and merge through a pull request.
- Do not commit directly to `main` during normal development.
- Use descriptive branch names such as:
  - `feat/new-shading-mode`
  - `fix/manual-override`
  - `docs/update-readme`
  - `refactor/config-normalization`
- Keep a branch focused on one coherent change or closely related set of
  changes.
- Do not mix dependency updates, release tooling, and runtime behavior changes
  in the same branch unless explicitly requested.

## Commits

- Antigravity and Codex must split logically independent changes into separate
  Conventional Commits.
- Keep implementation and its directly related regression tests in the same
  commit when they form one logical change.
- Allowed types are `feat`, `fix`, `docs`, `refactor`, `test`, `ci`, `build`,
  `chore`, `style`, `perf`, and `revert`.
- Scopes must use lowercase alphanumeric characters with hyphens, underscores,
  slashes, or dots (e.g. `runtime`, `config`, `release`).
- Breaking-change markers (`!`) are supported immediately after the type or
  scope, for example:

  `feat(config)!: change configuration schema`

- Subject lines must not end with a trailing period.
- Do not use vague aggregate messages such as:
  - `update files`
  - `changes`
  - `fix stuff`
  - `cleanup`
- Commit subjects should describe the observable purpose of the change.
- Validate commits locally using:

```sh
python scripts/validate_commit.py --message "<subject>"
```

- Before finishing a branch, validate the complete commit range:

```sh
python scripts/validate_commit.py --range origin/main..HEAD
```

## Pull requests

- Pull-request titles must follow the same Conventional Commit format, for
  example:

  `feat(runtime): improve adaptive cover positioning`

- The Conventional Commits workflow validates the PR title and every commit in
  the PR via `scripts/validate_commit.py`.
- Keep both the PR title and all commits valid before requesting review or
  merge.
- The pull request should describe:
  - the behavioral change;
  - important implementation decisions;
  - tests added or updated;
  - verification commands actually run;
  - known limitations, if any.
- Do not include unrelated changes in the pull request.

## Versions and release files

- Do not modify version files, release metadata, changelog entries, tags, or
  release workflows as part of an ordinary feature, fix, refactor, test, or
  documentation task unless the user explicitly requests release-related work.
- Do not manually bump:
  - `custom_components/cover_control/manifest.json`
  - release metadata
  - tags
  - release notes
  merely because runtime code changed.
- Do not create or modify `cover_control.zip` as part of normal development.
- Generated release archives must not remain in the working tree.

## Releases

- Release Drafter maintains release notes and resolves semantic version bumps:
  breaking changes are major, features are minor, and fixes are patch releases.
- Tags do not use a leading `v`.
- Only prepare or publish a release when the user explicitly requests it.
- Never invent a version number for an ordinary code change.
- Use the manual **Create Release** workflow with an explicit version and one of:
  - `draft`
  - `prerelease`
  - `release`
- The workflow updates
  `custom_components/cover_control/manifest.json` via
  `scripts/set_version.py`, commits the version as:

  `chore(release): <version>`

  verifies and attaches `cover_control.zip` via
  `scripts/build_release.py` and `scripts/verify_release.py`, and then applies
  the requested release state.
- Do not create release tags or GitHub releases outside the workflow.
- `.github/workflows/release-build.yml` is only the manual repair path for the
  HACS archive of an already-published release.
- Do not use the repair workflow to create a new release.
- If release verification fails, do not publish or partially repair the release
  by bypassing the verification scripts.

## Final review

Before reporting a task as complete:

1. Review `git status`.
2. Review `git diff origin/main...HEAD`.
3. Run the relevant focused tests.
4. Run the full test suite.
5. Run `compileall`.
6. Run `git diff --check`.
7. Validate all branch commit messages.
8. Confirm translations are synchronized when user-facing text changed.
9. Confirm no temporary, generated, debug, or release files were added.
10. Confirm no unrelated user changes were modified.
11. Confirm release/version files were untouched unless release work was
    explicitly requested.
12. Report only verification steps that were actually executed.

If any required verification could not be completed, state exactly what was not run and why.