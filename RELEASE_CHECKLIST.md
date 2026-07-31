# Final Release Checklist

## Source and Architecture

- [x] Legacy proof-of-concept packages, bytecode, logs, screenshots, and debug output removed.
- [x] Runtime/test fixture data separated.
- [x] Layer boundaries and source-of-truth documentation audited.
- [x] No interactive `input()` or batch-file pause remains.
- [x] Repository working tree is clean after the release commit.

## Quality Gates

- [x] Ruff passes.
- [x] Strict mypy passes against the available interpreter/stubs.
- [x] Unit, integration, E2E simulation, performance, and soak tests pass.
- [x] Production database validation passes.
- [x] Configuration validation passes.
- [x] CLI help and non-hardware commands pass.
- [ ] Opt-in real-device E2E passes on every supported production device.
- [x] Autonomous command execution is implemented with mandatory fresh-frame verification.
- [ ] Autonomous input acceptance passes on a physical production device.

## Packaging and Installation

- [x] Runtime dependencies match imported production libraries.
- [x] Console entry point is declared.
- [x] Database and template data-files are declared for packaging.
- [x] Windows scripts use `.venv`, explicit exit codes, and the production entry point.
- [ ] Clean online Windows installation verified by a release operator.
- [ ] Wheel and sdist built and installed in isolated Python 3.11, 3.12, and 3.13 environments.

## Operations and Security

- [x] Metrics, diagnostics, artifacts, and debug images are configuration controlled.
- [x] Artifact retention is bounded.
- [x] No credentials or environment values are included in diagnostics.
- [x] Troubleshooting and limitations are documented.
- [ ] Dependency vulnerability scan completed in the release environment.

## Release Decision

**NO-GO pending physical-device acceptance.** Autonomous command execution is implemented,
but complete game data, production templates, Android motion-event compatibility, and a
successful multi-level real-device run remain required before a production GO.
