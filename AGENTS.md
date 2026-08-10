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
`pytest-homeassistant-custom-component==0.13.355`. Run:

```sh
python -m pytest -q --asyncio-mode=auto
python -m compileall -q custom_components tests
git diff --check
```

Do not claim tests passed unless the command was actually run. If dependencies
are unavailable, report that limitation explicitly.

## Git and releases

- Develop on a feature branch and merge through a pull request. Do not commit
  directly to `main` unless the user explicitly requests it.
- Use Conventional Commit titles. `feat` causes a minor release, `fix` a patch
  release, and `feat!`/`fix!` a major release. `chore`, `docs`, `ci`, `refactor`,
  and `test` do not normally publish a release.
- Release Please owns `CHANGELOG.md`, `version.txt`,
  `.release-please-manifest.json`, and the `version` field in
  `custom_components/cover_control/manifest.json`. Do not bump these manually.
- Do not create release tags or GitHub releases manually. Merging the Release
  Please PR publishes the release and attaches `cover_control.zip` for HACS in
  the same workflow. `.github/workflows/release-build.yml` is only the manual
  repair path for an existing release.
- A failed asset build can be repaired with the workflow's manual dispatch and
  the already-published tag.
