# Change Log

## 0.2.0

- Added a visible BIBER Activity Bar change-agent view.
- Added a status bar entry so setup is discoverable after install.
- Added guided API setup for endpoint, model, and SecretStorage API key entry.
- Added a dedicated VS Code Activity Bar SVG while keeping the supplied PNG as
  the Marketplace icon.
- Continued `Test API Connection` and `Plan Change` after setup when users
  start those commands before storing an API key.
- Renamed the orchestration command title to `BIBER: Plan Change`.

## 0.1.2

- Replaced the Marketplace icon with the supplied BIBER AI logo artwork.

## 0.1.1

- Added the packaged Marketplace PNG icon for Visual Studio Marketplace listing display.

## 0.1.0

- Initial BIBER AI Assistant release.
- Added secure API-key storage through VS Code SecretStorage.
- Added `BIBER: Test API Connection` for `/v1/agent/capabilities`.
- Added `BIBER: Plan With BIBER Orchestration` for planning-only orchestration.
- Added client-side single-flight, timeout, rate-limit, HTTPS-or-localhost, and
  bounded prompt/path guards.
- Sends no file contents and performs no direct file mutation in this release.
