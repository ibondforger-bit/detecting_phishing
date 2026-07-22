# Phishing Detection Extension — V2.0.0 Update Plan
*Desktop Application + Local Backend*

---

## Overview

V2.0.0 introduces a **Windows desktop application** built with **PyQt6** that runs the backend process locally on the user's machine. The Chrome extension connects to this local desktop app instead of a remote server. This version targets a more technical audience.

---

## 1. Technology Stack (V2 Changes)

| Component | V1 | V2 |
|-----------|----|----|
| Backend location | Developer-run remote server | Local desktop app on user's machine |
| Desktop app framework | None | PyQt6 (Python) |
| Caching | Redis | diskcache (Python library, file-based, supports expiry, no extra installation needed) |
| Extension communication | Remote server via HTTPS | localhost (desktop app exposes local server) |
| Platform | Any (server-based) | Windows only |
| API key storage | Server `.env` file | `keyring` — Windows Credential Manager (OS-level encryption) |
| Cache | Redis | `diskcache` — file-based, Python-native, supports expiry |

**Why diskcache over Redis for Windows:**
- Works natively on Windows with zero extra installation
- Bundled inside the desktop app — user installs nothing separately
- Supports key expiry (important — cached phishing/safe verdicts shouldn't last forever)
- Behaviour closest to Redis among Python-native alternatives

---

## 2. Desktop Application (PyQt6)

### 2.1 System Tray Integration
- All backend processes run silently in the background
- System tray icon (bottom-right corner of Windows taskbar) shows current status:
  - 🟢 Green — running and protected
  - 🟡 Yellow — protection paused (user stopped it)
  - 🔴 Red — error or not working
- User clicks tray icon to open the full desktop app window
- Closing the window does not stop the backend — it returns to tray

### 2.2 Start / Stop Backend Control
- Simple Start / Stop button in the desktop app
- When stopped:
  - Extension shows: *"Protection is paused"* (user intentionally stopped it)
- When desktop app is unreachable or crashed:
  - Extension shows: *"The server is not working"*
- Two clearly different messages for two different situations

### 2.3 Auto-Start with Windows
- During first launch setup, user is offered an option:
  - *"Start PhishGuard automatically when Windows starts"* — checkbox, off by default
- If enabled: desktop app is added to Windows startup (via registry or Task Scheduler)
- User can enable/disable this anytime from desktop app settings
- Ensures protection is always active without the user remembering to open the app

### 2.4 API Key Management
- User enters their own API keys for any or all of the 5 blocklist APIs
- Keys are optional — if a key is not entered, that API is simply skipped
- Keys stored securely using `keyring` Python library — backed by Windows Credential Manager (OS-level encryption, most secure option for Windows)
- API key status shown per key: Active / Not configured
- No minimum number of keys required — system works with whatever is provided

### 2.5 Blocklist API Logic (Replaces Majority Vote)
- No majority vote in V2
- Each active API runs independently
- If **any** API flags a URL as phishing → popup names it directly:
  - *"Google Safe Browsing is showing phishing"*
  - *"VirusTotal and PhishTank are showing phishing"* (if multiple flag it)
- If no APIs are configured → fast tier runs URL pattern heuristics only, shows warning if patterns match
- Transparent — user always knows exactly which API raised the flag

### 2.6 Logs & Reports in Desktop App
- All logs and deep scan results displayed in the desktop app
- **Logs section:** full browsing history (date-time, URL, source, fast-tier flag, deep scan run, user action, note)
- **Reports section:** detailed deep scan summaries — one section per tool (WHOIS, DNS, DOM, NLP, redirect chain, network traffic)
- Extension popup shows fast flag only — full details always in desktop app
- Log export (CSV/PDF) — future update

### 2.7 Manual URL Scan in Desktop App
- User can paste any URL directly into the desktop app and trigger a deep scan without visiting the site
- Same deep scan pipeline as browser-triggered scans (WHOIS, DNS, DOM, redirect, network traffic)
- Results saved to logs and shown in reports section
- Also accessible from extension: existing Deep Scan button in popup triggers scan and results appear in desktop app

### 2.8 Whitelist Management in Desktop App
- User can view the full whitelist (all trusted domains)
- Add custom trusted domains (personal whitelist additions)
- Remove domains they don't trust
- Base whitelist (finance, government, social media, shopping, news) pre-loaded from `whitelist_fast.json`
- User additions stored locally, separate from the base whitelist file

### 2.9 Basic Stats Dashboard

A summary panel visible at the top of the desktop app at all times showing:

| Stat | Description |
|------|-------------|
| Sites scanned today | Total navigations checked by fast tier today |
| Sites flagged today | How many were flagged as suspicious today |
| Total scanned (all time) | Lifetime fast tier check count |
| Total flagged (all time) | Lifetime suspicious flag count |
| Deep scans run | Total number of deep scans triggered by user |
| Most active API | Which blocklist API has flagged the most URLs |
| Last scan time | Timestamp of the most recent fast tier check |

Stats are calculated from the local log file — no extra data collection needed.

---

## 3. Extension ↔ Desktop App Communication

### 3.1 How They Talk
- Desktop app exposes a local HTTP server on `localhost:5000` (default port)
- Chrome extension sends all requests to `localhost:5000` instead of remote server
- Same API endpoints as V1 (`/check`, `/deepscan`, `/whitelist`) — just different host

### 3.2 Health Check (Keeping Each Other Alive)
- Extension pings `localhost:5000/health` every 30 seconds
- Desktop app responds with current status: `{ "status": "running" }` or `{ "status": "paused" }`
- If ping fails (no response):
  - Extension shows: *"The server is not working"* in popup
  - Extension fails open — links load normally, no scanning
- If user stopped the backend intentionally:
  - Desktop app responds with `{ "status": "paused" }`
  - Extension shows: *"Protection is paused"*

### 3.3 Port Conflict Fallback
- If port 5000 is already in use on the user's machine, desktop app tries: 5001 → 5002 → 5003
- Extension is notified of the active port on startup
- Active port stored locally so extension always knows where to connect

---

## 4. Installation & Onboarding Flow

### 4.1 Full Step-by-Step Workflow

```
STEP 1 — DOWNLOAD
  User downloads PhishGuard-Setup.exe from the website
       ↓
STEP 2 — INSTALL
  User runs the .exe installer
  Installer silently sets up:
    - Desktop app (PyQt6)
    - All Python dependencies:
        FastAPI, PyQt6, diskcache, python-whois,
        dnspython, httpx, BeautifulSoup, Celery, keyring
    - Local folder structure:
        /PhishGuard
          /cache       ← diskcache files
          /logs        ← browsing log JSON
          /outputs     ← deep scan JSON results
          /whitelist   ← whitelist_fast.json
  No manual Python installation required — all bundled
       ↓
STEP 3 — FIRST LAUNCH
  Desktop app opens automatically after install
  Setup wizard appears (one-time only)
       ↓
STEP 4 — SETUP WIZARD

  ┌─ WIZARD STEP 1: API Keys (optional) ──────────────────┐
  │                                                         │
  │  Enter your API keys for any of the 5 blocklist APIs:  │
  │    □ Google Safe Browsing  [____________] (optional)    │
  │    □ PhishTank             [____________] (optional)    │
  │    □ Cloudflare            [____________] (optional)    │
  │    □ Spamhaus              [____________] (optional)    │
  │    □ VirusTotal            [____________] (optional)    │
  │                                                         │
  │  Can skip — system works with URL heuristics only       │
  │  Keys saved to Windows Credential Manager (keyring)     │
  │  Can add/change anytime from Settings                   │
  └─────────────────────────────────────────────────────────┘
       ↓
  ┌─ WIZARD STEP 2: Auto-Start (optional) ────────────────┐
  │                                                         │
  │  □ Start PhishGuard automatically when Windows starts   │
  │    (off by default, user chooses)                       │
  │                                                         │
  │  If enabled: added to Windows startup via registry      │
  │  Can change anytime from Settings                       │
  └─────────────────────────────────────────────────────────┘
       ↓
  ┌─ WIZARD STEP 3: Chrome Extension ─────────────────────┐
  │                                                         │
  │  Install the PhishGuard Chrome Extension:               │
  │  [Open Chrome Web Store →]                              │
  │                                                         │
  │  Wizard waits and checks every 5 seconds...             │
  │    - Extension not detected: "Waiting for extension..." │
  │    - Extension detected + connected:                    │
  │      ✅ "Desktop app and extension are connected"       │
  └─────────────────────────────────────────────────────────┘
       ↓
STEP 5 — SETUP COMPLETE
  Wizard closes
  System tray icon appears — 🟢 Green (running, protected)
  Desktop app window minimises to tray
       ↓
STEP 6 — NORMAL USE BEGINS
  User browses normally in Chrome
  Extension intercepts every navigation
  Desktop app processes checks silently in background
  User opens desktop app anytime from tray icon
```

### 4.2 Returning User Flow (After First Setup)

```
Windows starts
       ↓
  ┌─ Auto-start enabled? ─────────┐
  │ Yes → PhishGuard starts       │
  │       silently in background  │
  │       Tray icon appears 🟢    │
  │                               │
  │ No  → User opens PhishGuard   │
  │       manually when needed    │
  └───────────────────────────────┘
       ↓
User opens Chrome → protection active immediately
```

### 4.3 Connection Lost Flow

```
Extension pings localhost:5000/health every 30 seconds
       ↓
  ┌─ Response received? ───────────────────────────────────┐
  │                                                         │
  │  { "status": "running" }                                │
  │  → Everything normal, continue                          │
  │                                                         │
  │  { "status": "paused" }                                 │
  │  → User stopped it intentionally                        │
  │  → Extension shows: "Protection is paused"              │
  │  → Links load normally (fail open)                      │
  │                                                         │
  │  No response / timeout                                  │
  │  → Desktop app crashed or not running                   │
  │  → Extension shows: "The server is not working"         │
  │  → Links load normally (fail open)                      │
  └─────────────────────────────────────────────────────────┘
```

---

## 5. Features Deferred to Future Updates

| Feature | Reason Deferred |
|---------|----------------|
| Log export (CSV / PDF) | V1 shows all logs — export added later |
| Windows native notifications | Added after core V2 is stable |
| ~~Basic stats dashboard~~ | ✅ Added to V2 (Section 2.9) |
| Multi-browser support (Edge, Firefox) | After Windows V2 is stable |
| Mac / Linux support | After Windows V2 is stable |
| Auto-update mechanism | After first stable public release |
| "Bring your own API key" advanced mode (from V1 roadmap) | Covered by V2 API key management — effectively done |

---

## 6. What Stays the Same from V1

- Chrome extension UI (interstitial page, warning popup, three buttons: Continue / Deep Scan / Go Back)
- Fast tier detection logic (URL pattern heuristics, whitelist check)
- Deep scan tools (WHOIS, DNS, DOM, redirect chain, network traffic — 2 hops on unknown domains)
- NLP analysis (developer-handled separately, output saved as JSON)
- System LLM placeholder (still deferred, JSON outputs saved ready for later)
- User exclusion list
- Notes on Continue or Deep Scan
- Full browsing log format
- `whitelist_fast.json` base file

---

## 7. Resolved Decisions

| # | Topic | Decision |
|---|-------|----------|
| 1 | Basic stats dashboard | ✅ Added to V2 — Section 2.9 |
| 2 | API key encryption | ✅ `keyring` library — Windows Credential Manager backed |
| 3 | Deep scan results format | ✅ JSON — same structured format as V1 |

---

*Document version: V2.0.0 Planning | Status: Discussion phase*
