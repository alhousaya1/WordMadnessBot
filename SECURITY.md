# Security Policy

## Reporting

Report suspected vulnerabilities privately to the repository owner. Do not include device
serials, screenshots, logs, credentials, or proprietary level data in public reports.

## Operational Guidance

Use only trusted ADB and Tesseract executables, keep Android debugging access physically
controlled, validate `levels.json`, and do not run unreviewed templates or databases.
Diagnostics intentionally exclude environment values and screenshots by default. Pin and
scan dependencies in the release environment before deployment.

## Supported Version

Version 0.1.x receives security fixes while under active development. It is not approved
for unattended autonomous production operation; see `RELEASE.md` and
`RELEASE_CHECKLIST.md`.
