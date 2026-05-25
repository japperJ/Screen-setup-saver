# Browser Capture UX + Profiles Pane + Cross-Browser Restore Design

Date: 2026-05-25  
Project: Screen Setup Saver

## 1. Problem Summary

The current behavior creates confusion in three places:

1. Browser URLs are only captured when Chrome/Edge are launched with remote debugging enabled.
2. The Profiles tab details panel is below the list, which is hard to scan and wastes horizontal space.
3. Restoring one URL per two different browsers can still open both in the same browser in some cases.

## 2. Key Constraint (Important)

For Chrome and Edge, tab URL capture is obtained via CDP (`/json/list`).  
Without CDP/debug mode, there is no stable, supported API for this app to read all open tab URLs.

**Conclusion:** we cannot reliably remove debug-mode requirement for URL capture.  
We should instead make setup and status clear and one-click friendly.

## 3. Approaches Considered

### Approach A — Keep as-is, add documentation only
- Pros: minimal change.
- Cons: still confusing, poor discoverability, repeated support friction.

### Approach B — Guided capture UX + explicit browser restore routing (**Recommended**)
- Pros: clear user flow, fewer failed saves, easier troubleshooting, fixes cross-browser URL restore routing.
- Cons: moderate UI and restore logic changes.

### Approach C — Browser extension/native host integration
- Pros: could avoid debug mode for some browsers.
- Cons: high complexity, distribution burden, maintenance overhead, browser policy constraints.

## 4. Recommended Design

## 4.1 Browser Setup: Make Capture Mode User-Friendly

Enhance **Settings → Browser Setup** with:

1. **Capture readiness indicators** for Chrome/Edge:
   - “Connected” / “Not connected” for configured ports.
   - Last successful URL count.
2. **One-click launch buttons**:
   - “Launch Chrome in Capture Mode”
   - “Launch Edge in Capture Mode”
   - Use configured ports and bind address `127.0.0.1`.
3. **Quick verification action**:
   - “Test browser capture now” and show result summary (e.g., `Chrome: 3, Edge: 1`).
4. **Clear helper text**:
   - URLs are captured only while browser process was started in capture mode.
   - Normal launches won’t expose tabs.

This removes the need for users to run PowerShell commands manually.

## 4.2 Profiles Tab Layout: Side-by-Side Details

Replace current vertical stack with horizontal split:

- **Left pane**: saved profile list + action buttons.
- **Right pane**: “Selected profile details”.

Details pane includes:
- Windows captured count.
- Browser tabs captured total.
- Per-browser breakdown:
  - Chrome URLs
  - Edge URLs
- Distinct app executables summary.

If no URLs are saved, show a clear message:
“No browser URLs were saved in this profile. Start the browser in Capture Mode before saving.”

## 4.3 Restore Bug Fix: Keep Browser URL Restore Browser-Specific

Current fallback can route URLs to default browser when target browser executable is not resolved.

Design change:

1. At save time, persist optional **browser executable hints**:
   - `browser_exes.chrome`
   - `browser_exes.edge`
2. At restore time, resolve browser executable by priority:
   - Saved `browser_exes` hint
   - Installed known paths
   - Existing matching running window executable
   - Only then fallback to `webbrowser.open` (with warning)
3. Log explicit routing decisions:
   - “Restoring Chrome URL via …”
   - “Chrome executable not found; default browser fallback used.”

This keeps one-url-per-browser restores from collapsing into default-browser tabs where possible.

## 5. Data Model Updates

Profile JSON (additive, backward compatible):

```json
{
  "windows": [...],
  "browser_tabs": {
    "chrome": ["..."],
    "edge": ["..."]
  },
  "browser_exes": {
    "chrome": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "edge": "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe"
  }
}
```

If `browser_exes` is absent (old profiles), restore uses existing path detection.

## 6. Error Handling + UX Messaging

Add user-facing guidance on save:

- If browser capture returns empty for both browsers:
  - Save still succeeds.
  - Show non-blocking message: “No browser tabs captured. Launch browsers in Capture Mode to include URLs.”

In profile details pane:
- Show latest captured counts to reduce guesswork before restore.

## 7. Testing Strategy

1. **Unit tests (browser restore routing)**
   - Uses saved hint path when available.
   - Falls back correctly when hint missing.
   - Warns on default-browser fallback.
2. **Unit tests (profile details formatting)**
   - Side pane shows per-browser URL counts and values.
3. **Integration-style tests**
   - Profile with one Chrome URL + one Edge URL routes to distinct browser executables.
4. **Regression tests**
   - Existing window restore behavior remains unchanged.

## 8. Scope / Non-Goals

In scope:
- UX and reliability for browser URL capture/restore and profile clarity.

Out of scope:
- Eliminating debug-mode requirement via unsupported browser internals.
- Full UI framework rewrite.

## 9. Rollout Notes

1. Implement Browser Setup guided actions first.
2. Implement profile side-by-side layout and details.
3. Implement browser-specific restore routing with saved executable hints.
4. Validate with real save/restore scenarios:
   - Chrome only
   - Edge only
   - Both browsers with different URLs
