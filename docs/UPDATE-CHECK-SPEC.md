# Nenolink AI Marker — Update Check Specification

Target: 1.0.1

Purpose: make it possible to notify installed 1.0.x customers when Nenolink publishes a bug fix or later release, without turning AI Marker into an automatic installer.

## Scope

AI Marker checks a small HTTPS JSON document hosted on nenolink.com. The application does not download or install software automatically.

Automatic checks occur at most once every 30 days. A manual `Check for updates` action is also provided.

The network request must run outside the Tk UI thread and use a short timeout so startup and normal offline use are never blocked by a slow or unavailable server.

If the check fails, normal application operation continues. Automatic failures are silent. A manual check may report a concise error.

## User interface

When the server reports a newer version, display a red clickable link in the application header, for example:

`New version available: 1.0.2`

Clicking the link opens the official Nenolink update page in the user's default browser.

If the installed version is current, no red notification is shown.

The update page, not the desktop application, owns the download button and release information.

## Version manifest

Recommended public location:

`https://nenolink.com/downloads/ai-marker/latest.json`

Recommended payload:

```json
{
  "schema": 1,
  "latest_version": "1.0.1",
  "release_date": "2026-09-10",
  "update_url": "https://nenolink.com/en/aimarkerupdate/",
  "minimum_supported_version": "1.0.1"
}
```

Only HTTPS URLs on an approved Nenolink domain may be opened from manifest data. Do not accept executable paths or commands from the manifest.

The manifest must remain small and contain no secrets, customer data, licence keys or Stripe data.

## Persistent settings

Add fields to the existing per-user settings model:

- `automatic_update_check`: boolean, default `true`;
- `last_update_check`: ISO date/time string, empty until the first completed automatic check.

A completed HTTP/JSON check updates `last_update_check`. A failed network request should not repeatedly retry during the same application session.

## Privacy and network behaviour

Image/video processing remains local. The update request must not upload media, filenames, file paths, badge choices, logo information, licence information or other user content.

No unique installation ID is required.

The HTTP server will inherently receive ordinary connection information such as an IP address and standard request headers. Website/server privacy and retention practices therefore apply to update checks.

Privacy/FAQ text should disclose that, when automatic update checking is enabled, the application periodically contacts nenolink.com solely to obtain current release information.

## Security

- HTTPS only.
- Short network timeout (recommended 3–5 seconds).
- Strict JSON parsing and field validation.
- Use semantic/version-aware comparison rather than string comparison.
- Do not execute any content returned by the server.
- Do not download an EXE/ZIP in the background.
- Do not send Stripe secrets or customer/session information.
- Open only an approved Nenolink update URL in the default browser.

Python's standard `urllib.request` is sufficient for the small HTTPS GET and supports an explicit timeout. The existing packaged `packaging` dependency can provide comparison-aware `Version` objects.

## Update web page

Create a public update page on nenolink.com with at least:

- Nenolink AI Marker — Updates;
- current version;
- release date;
- concise changes/fixes;
- whether the update is included for 1.x licence holders;
- Windows download button;
- SHA-256 of the current ZIP;
- link to user guide;
- installation note: close AI Marker, extract/install the new release, settings remain in the user's AppData profile;
- support contact.

The download button must use the existing protected fulfilment design. Do not expose the ZIP as a direct public URL.

For 1.x, the update page may provide an authenticated/protected download route for existing customers. A later paid major version may instead show upgrade/purchase instructions.

## Acceptance tests

1. Installed 1.0.1 + manifest 1.0.1: no red link.
2. Installed 1.0.1 + manifest 1.0.2: red link appears with 1.0.2.
3. Clicking notification opens only the approved Nenolink update page.
4. No network: application starts and works normally.
5. Timeout/server 500/404: application remains usable.
6. Invalid JSON: ignored safely.
7. Invalid/missing version: ignored safely.
8. Malicious/non-Nenolink update URL: never opened.
9. Automatic check is not repeated before 30 days.
10. Manual check works regardless of the 30-day interval.
11. Automatic update checking can be disabled and persists.
12. No media/user-content fields are transmitted.
13. Existing 1.0.0 settings load without error after the new settings fields are introduced.
14. Packaged Windows EXE performs the check without blocking the UI.

## Release rule

The verified/tagged 1.0.0 release remains unchanged. Implement, test, package and tag this feature as 1.0.1. Do not silently replace the 1.0.0 binary or tag.
