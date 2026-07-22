# WebSense Chrome Extension — Workflow Document
*Phase 2: Complete Implementation & Setup Guide*

---

## 1. Implementation Checklist

This document outlines the complete workflow for building and testing the WebSense Chrome Extension. The approach is: **build all components fully first, then test everything together.** Each section describes what to build, how to build it, and what it should do when done correctly.

---

## Phase 1 — Build

### 1.1 Set Up the Project Environment

**What to do:**
Set up the folder structure, install all required tools, and make sure the development environment is ready before writing any feature code.

**Tasks:**
- [ ] Create the project folder structure:
  ```
  /extension        ← Chrome extension files
  /server           ← Python backend files
  /whitelist        ← Whitelist data files
  /outputs          ← Saved deep scan JSON outputs
  ```
- [ ] Initialize Git repository and connect to GitHub
- [ ] Set up Python virtual environment for the server
- [ ] Install Python dependencies: `fastapi`, `uvicorn`, `python-whois`, `dnspython`, `httpx`, `beautifulsoup4`, `celery`, `redis`, `python-dotenv`
- [ ] Install and run Redis locally
- [ ] Create `.env` file for API keys (Google Safe Browsing, VirusTotal, PhishTank, Cloudflare, Spamhaus)
- [ ] Set up VS Code with Python and JavaScript extensions

**Done when:** Project runs locally with no errors, Redis is running, and all dependencies are installed.

---

### 1.2 Build the Chrome Extension (Frontend)

**What to do:**
Build the Chrome extension — the part that runs inside the user's browser. It intercepts every navigation, communicates with the server, shows the popup, and manages local storage.

#### 1.2.1 Manifest File
- [ ] Create `manifest.json` using Manifest V3
- [ ] Declare required permissions: `declarativeNetRequest`, `webRequest`, `storage`, `tabs`, `webNavigation`
- [ ] Register background service worker, popup, and interstitial page

#### 1.2.2 Interstitial Page (the "checking" page)
- [ ] Create `interstitial.html` — the page shown for 0.5–2 seconds while fast tier runs
- [ ] Show a neutral message: *"Checking this site..."* with a loading indicator
- [ ] On fast tier result:
  - Safe → redirect user to the original URL automatically
  - Suspicious → show warning popup in place (do not redirect)

#### 1.2.3 Warning Popup
- [ ] Create the warning popup UI inside the interstitial page
- [ ] Display the flagged URL clearly
- [ ] Show message: *"This site might be suspicious."*
- [ ] Three action buttons:
  - **Continue** → opens the site, creates a log entry, no scan
  - **Deep Scan** → opens the site + triggers deep scan on server + note prompt appears
  - **Go Back** → closes the tab or returns to previous page, no log entry, no scan
- [ ] Add optional note field (short text input, appears on Continue or Deep Scan, skippable)
- [ ] Add **Open Dashboard** button (always visible in popup, separate from the three action buttons)
  - Opens extension dashboard in a new browser tab
  - Available on both the warning popup and the normal extension icon popup

#### 1.2.4 Report Panel
- [ ] Create `report.html` — a full page showing deep scan results
- [ ] Display one section per tool: WHOIS, DNS, DOM, NLP, redirect chain, network traffic
- [ ] Read results from saved JSON (loaded from server after scan completes)
- [ ] Accessible via extension icon for any recently scanned site
- [ ] Placeholder section at top for future LLM plain-English description

#### 1.2.5 Extension Dashboard (New Browser Tab)

**What to do:**
Build a full-page dashboard that opens in a new browser tab when the user clicks "Open Dashboard." It has two sections: API key status and deep scan results history.

- [ ] Create `dashboard.html` — full browser tab page
- [ ] Register it in `manifest.json` as an extension page

**API Keys Settings section:**
- [ ] Show status of all 5 blocklist API keys (Active / Inactive) — no key values shown to regular users, keys are stored server-side
- [ ] Admin view: ability to update server-side API keys (Google Safe Browsing, VirusTotal, PhishTank, Cloudflare, Spamhaus)
- [ ] Show current rate limit status per API (requests remaining today/this month where available)

**Deep Scan Results History section:**
- [ ] Load all past deep scan JSON outputs from server
- [ ] Display as a browsable list — each entry shows: URL, date/time, scan ID
- [ ] Clicking an entry expands to show full tool-by-tool results (same layout as report panel)
- [ ] Placeholder section visible at top of each result for future LLM plain-English description
- [ ] Empty state message if no scans have been run yet

**Done when:** Dashboard opens correctly from popup button, API key statuses display accurately, and past scan results load and display correctly.

---

#### 1.2.5 Background Service Worker
- [ ] Intercept all main-frame navigations using `declarativeNetRequest`
- [ ] Redirect every navigation to the interstitial page first
- [ ] Send URL (SHA256 hash first, raw URL on cache miss) to server for fast tier check
- [ ] Receive fast tier result and pass to interstitial page
- [ ] Handle Deep Scan button click → send raw URL to server deep scan endpoint
- [ ] Listen for deep scan completion → make report available

#### 1.2.6 Local Storage Management
- [ ] Save log entries to `chrome.storage.local` on every navigation (format: date-time, source, URL, time spent, fast-tier flag, deep scan run, user action, note)
- [ ] Save and load user exclusion list from `chrome.storage.local`
- [ ] Fetch and cache whitelist (fast lookup set) from server daily

**Done when:** Extension loads in Chrome Developer Mode without errors, interstitial page appears on every navigation, and all three popup buttons work correctly.

---

### 1.3 Build the Backend Server (Python + FastAPI)

**What to do:**
Build the server that handles all the heavy work — fast tier checks, deep scan tools, caching, and whitelist serving.

#### 1.3.1 Project Structure
```
/server
  main.py              ← FastAPI app entry point
  /routers
    fast_tier.py       ← Fast tier endpoint
    deep_scan.py       ← Deep scan endpoint
    whitelist.py       ← Whitelist serving endpoint
  /tools
    whois_tool.py
    dns_tool.py
    dom_tool.py
    redirect_tool.py
    network_tool.py
  /cache
    redis_client.py    ← Redis connection and helpers
  /outputs             ← Saved JSON scan results
  .env                 ← API keys and config
```

#### 1.3.2 Fast Tier Endpoint
- [ ] Create `POST /check` endpoint — receives SHA256 hash, checks Redis cache first
- [ ] On cache miss: receive raw URL, run blocklist checks in priority order:
  1. Google Safe Browsing API
  2. PhishTank API (or local hourly database)
  3. Cloudflare API
  4. Spamhaus API
  5. VirusTotal API (tiebreaker only — called when first four split 2–2)
- [ ] Apply majority vote logic: 3 or more agree → verdict decided
- [ ] Run URL pattern heuristics (lookalike characters, suspicious TLDs, IP-as-domain, brand in subdomain, hyphenated brand, URL-encoded characters, long URLs, HTTP on credential pages, phishing keywords)
- [ ] Check against whitelist fast lookup (Redis SET)
- [ ] Store result in Redis cache (key: SHA256(URL))
- [ ] Return: `{ "result": "safe" | "suspicious", "reason": "..." }`

#### 1.3.3 Deep Scan Endpoint
- [ ] Create `POST /deepscan` endpoint — receives raw URL
- [ ] Use Celery to run all tools in parallel (not one by one):
  - `whois_tool.py` — domain age, registrar, registration date, privacy protection
  - `dns_tool.py` — DNS record consistency, nameserver check
  - `dom_tool.py` — fetch page HTML via `httpx`, parse with `BeautifulSoup`, check for login forms, hidden fields, credential inputs, form submission target domain
  - `redirect_tool.py` — follow redirect chain via `httpx`, record all hops
  - `network_tool.py` — identify unknown connected domains, run fast-tier scan on each (2 hops max, unknown domains only)
- [ ] NLP tool slot — reserved for developer's separate NLP implementation, output saved as JSON alongside other tools
- [ ] Save all tool outputs as structured JSON to `/outputs/{scan_id}.json`
- [ ] Return scan ID to extension so report panel can fetch results

#### 1.3.4 Whitelist Endpoint
- [ ] Create `GET /whitelist` endpoint — returns fast lookup list (domain names only, as a flat array)
- [ ] Maintain separate full JSON file with verification details (registrar, SSL issuer, registered since, aliases) — used only during deep scan WHOIS comparison
- [ ] Extension fetches fast lookup list daily and stores locally as a JS `Set`

#### 1.3.5 Error Handling (Full System)
- [ ] **Blocklist APIs:** if one times out or errors → skip it, continue with remaining. If all fail → return `"suspicious"` (fail safe)
- [ ] **Deep scan tools:** if any tool fails → save `{"status": "error", "reason": "..."}` in that tool's JSON slot, continue with others
- [ ] **Server unreachable:** extension shows message: *"Could not check this site — no connection to scan server."* User still gets Go Back option
- [ ] **Redis cache failure:** bypass cache, run fresh check. If fresh check also fails → return `"suspicious"`
- [ ] **Rate limits hit:** skip that API for the current request, log the event server-side
- [ ] **Request timeout:** configurable timeout (default 5 seconds), fail safe on expiry
- [ ] **Storage full (`chrome.storage.local`):** alert user, prompt to clear old log entries
- [ ] All server-side errors logged for debugging. No error ever silently passes a URL as safe.

**Done when:** All endpoints respond correctly in Postman, Redis caches results, Celery runs tools in parallel, and all error scenarios return safe fallback responses.

---

### 1.4 Build the Whitelist

**What to do:**
Build and populate the two whitelist files — one for fast lookup, one for deep scan verification.

- [ ] Create `whitelist_fast.json` — flat array of trusted domain names (used by extension as a JS `Set`)
- [ ] Create `whitelist_details.json` — full JSON with verification details per domain (used during deep scan WHOIS comparison)
- [ ] Populate with major categories: finance, email, social media, shopping, cloud/tech, government, news/entertainment
- [ ] Set up daily refresh endpoint so extension always has an up-to-date copy

**Done when:** Extension loads whitelist into memory on startup, known-safe domains pass fast tier instantly without hitting blocklist APIs.

---

## Phase 2 — Test

### 2.1 Testing Approach

All components are built before testing begins. Testing is done in three layers: **unit testing** (each tool individually), **integration testing** (components working together), and **end-to-end testing** (full user journey in the real browser).

---

### 2.2 Unit Tests — Individual Tools

Test each backend tool in isolation with known inputs and expected outputs.

| Tool | Test Input | Pass Criteria |
|------|-----------|---------------|
| WHOIS tool | Known phishing domain (recent) | Returns domain age < 30 days, privacy-protected registrar |
| WHOIS tool | Known safe domain (e.g. google.com) | Returns domain age > 10 years, known registrar |
| DNS tool | Known phishing domain | Returns nameserver anomaly or inconsistency |
| DNS tool | Known safe domain | Returns clean, consistent DNS records |
| DOM tool | HTML with hidden credential form | Detects form, flags cross-domain submission target |
| DOM tool | Normal login page (e.g. GitHub) | No suspicious patterns flagged |
| Redirect tool | URL with 3 redirect hops | Records full chain, all hops logged |
| Network tool | Page loading from unknown domain | Flags unknown domain, runs fast-tier scan on it |
| URL heuristics | `paypa1.com`, `secure-paypal.login.com` | Flagged as suspicious |
| URL heuristics | `paypal.com`, `google.com` | Passed as clean |
| Blocklist APIs | Known phishing URL (from PhishTank database) | At least 3 of 5 APIs return positive |
| Majority vote | 3 safe + 1 suspicious (no VirusTotal needed) | Returns safe, VirusTotal not called |
| Majority vote | 2 safe + 2 suspicious | VirusTotal called as tiebreaker |

**Pass criteria:** Every tool returns structured JSON in the correct format. No tool crashes on bad input — error state is returned instead.

---

### 2.3 Integration Tests — Components Working Together

Test that the extension and server communicate correctly end-to-end.

| Scenario | Expected Result |
|----------|----------------|
| Extension sends SHA256 hash of cached URL | Server returns cached result instantly, no API calls made |
| Extension sends SHA256 hash of uncached URL | Server runs full fast tier, caches result, returns verdict |
| User clicks Deep Scan | Server runs all tools in parallel via Celery, saves JSON, returns scan ID |
| Extension fetches report by scan ID | Report panel loads correct JSON, displays all tool sections |
| Extension fetches whitelist | Returns flat domain array, extension stores as JS Set |
| Known whitelisted domain visited | Fast tier returns safe instantly, no blocklist APIs called |
| Server is unreachable | Extension shows "no connection" message, Go Back option available |
| All blocklist APIs fail | Server returns suspicious (fail safe), not safe |

**Pass criteria:** Every scenario behaves exactly as described. No silent failures.

---

### 2.4 End-to-End Tests — Full User Journey in Browser

Load the extension in Chrome Developer Mode and test real user journeys manually.

| Journey | Steps | Pass Criteria |
|---------|-------|--------------|
| Safe site visit | Visit google.com | Interstitial appears briefly, page loads normally, log entry created |
| Suspicious site — Continue | Visit known phishing URL, click Continue | Page opens, log entry saved with action = "Continue" |
| Suspicious site — Deep Scan | Visit known phishing URL, click Deep Scan | Page opens, scan runs, report panel shows all tool results |
| Suspicious site — Go Back | Visit known phishing URL, click Go Back | Page does not open, no log entry created |
| Note on Continue | Click Continue, add a note | Note saved with log entry |
| Note on Deep Scan | Click Deep Scan, add a note | Note saved with log entry |
| Note skipped | Click Continue, skip note | Log entry saved without note field |
| Exclusion list | Add `mybank.com` to exclusion list, visit it | No interstitial, no log entry |
| Whitelisted domain | Visit `paypal.com` | Fast tier passes instantly, no blocklist API calls |
| Extension icon — recent report | After Deep Scan, click extension icon | Report panel opens with scan results |
| Open Dashboard — from popup | Click Open Dashboard button in popup | Dashboard opens in new browser tab |
| Dashboard — API key status | Open dashboard, view API keys section | All 5 APIs show correct Active/Inactive status |
| Dashboard — scan history | Run a deep scan, open dashboard | Scan result appears in history list, expands correctly |
| Dashboard — empty state | Open dashboard before any scans | Empty state message shown in results history |

**Pass criteria:** Every journey completes without errors. Log entries are correct. Report panel displays accurate data.

---

### 2.5 Edge Case Tests

| Edge Case | Expected Behavior |
|-----------|------------------|
| User visits same phishing URL twice | Second visit returns cached result instantly |
| URL with encoded characters (`%70%61%79`) | Decoded and flagged by URL heuristics |
| Page with no forms or suspicious content | DOM tool returns clean result, no false positive |
| Redirect chain longer than 2 hops on unknown domains | Only 2 hops followed, rest ignored |
| `chrome.storage.local` quota exceeded | User alerted, prompted to clear old logs |
| Deep scan takes longer than expected | Report panel shows "scan in progress" state until complete |
| Two blocklist APIs return conflicting results | Majority vote applied correctly |

---

### 2.6 Final Check Before V2

- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] All end-to-end journeys complete correctly
- [ ] All edge cases handled without crashes
- [ ] Error handling verified — no silent safe passes on failure
- [ ] Log format is consistent and complete across all journey types
- [ ] Deep scan JSON outputs are saved correctly and readable by report panel
- [ ] NLP output slot is present in JSON structure, ready for developer's implementation
- [ ] LLM placeholder section visible in report panel, ready to connect later
- [ ] Dashboard opens correctly from popup Open Dashboard button
- [ ] Dashboard API key section shows correct status for all 5 APIs
- [ ] Dashboard scan history loads and displays all past deep scan results
- [ ] LLM placeholder visible in dashboard scan history entries
- [ ] Redis cache working — repeat URLs do not trigger fresh API calls
- [ ] Whitelist fast lookup working — known-safe domains bypass blocklist APIs

**Done when:** All boxes above are checked. The system is stable, consistent, and ready for V2 additions (System LLM, Google OAuth, Drive sync).

---

*Document version: V1 | Phase: Build + Test | Next phase: V2 planning after V1 testing is complete*
