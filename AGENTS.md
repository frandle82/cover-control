# Cover Control

Home Assistant custom integration for automated cover positioning. Runtime code
lives in `custom_components/cover_control/`; regression tests live in `tests/`.

## Working rules

- Preserve unrelated user changes in the working tree.
- Keep Home Assistant callbacks non-blocking. Use `async_` APIs and schedule or
  await I/O through Home Assistant's helpers.
- Put shared constants and defaults in `const.py`; keep the public controller
  imports stable through `controller.py`.
- Runtime behavior is split into focused mixins under
  `custom_components/cover_control/runtime/`. Add logic to the owning mixin
  instead of growing the facade.
- Keep `strings.json`, `translations/en.json`, and `translations/de.json` in
  sync whenever user-facing text changes.
- Add or update a regression test for every behavior change.

## Verification

Use an isolated virtual environment and install
`pytest-homeassistant-custom-component==0.13.365`. Run:

```sh
python -m pytest -q --asyncio-mode=auto
python -m compileall -q custom_components tests
git diff --check
```

Do not claim tests passed unless the command was actually run. If dependencies
are unavailable, report that limitation explicitly.

## Development

- Develop on a focused feature branch and merge through a pull request. Do not
  commit directly to `main` during normal development.
- Use descriptive branch names such as `feat/new-shading-mode`,
  `fix/manual-override`, or `docs/update-readme`.

## Commits

- Antigravity and Codex must split logically independent changes into separate
  Conventional Commits.
- Allowed types are `feat`, `fix`, `docs`, `refactor`, `test`, `ci`, `build`,
  `chore`, `style`, `perf`, and `revert`.
- Scopes and breaking-change markers are supported, for example
  `feat(runtime): improve sun protection calculation`,
  `fix(config): preserve manual cover override`, and
  `feat(config)!: change configuration schema`.
- Do not use vague aggregate messages such as `update files` or `changes`.

## Pull requests

- Pull-request titles must follow the same Conventional Commit format, for
  example `feat(runtime): improve adaptive cover positioning`.
- The Conventional Commits workflow validates the PR title and every commit in
  the PR. Keep both valid before requesting review or merge.

## Releases

- Release Drafter maintains release notes and resolves semantic version bumps:
  breaking changes are major, features are minor, and fixes are patch releases.
- Tags do not use a leading `v`.
- Only prepare or publish a release when the user explicitly requests it. Never
  invent a version number for an ordinary code change.
- Use the manual **Create Release** workflow with an explicit version and one of
  `draft`, `prerelease`, or `release`. The workflow updates
  `custom_components/cover_control/manifest.json`, commits the version as
  `chore(release): <version>`, verifies and attaches `cover_control.zip`, and
  then applies the requested release state.
- Do not create release tags or GitHub releases outside the workflow.
- `.github/workflows/release-build.yml` is only the manual repair path for the
  HACS archive of an already-published release.
