# WebSense Chrome Extension — Complete Plan
*Phase 1: Planning Document*

---

## 1. Project Overview

A Chrome extension that intercepts every URL a user navigates to, checks it against fast and deep detection systems, and warns non-tech-savvy users before they can hand over sensitive information on phishing sites.

**Model:** SaaS — developer runs the backend server. Users install the extension and use it with zero setup.

---

## 2. Core Architecture

### Two-tier detection system

Every navigation passes through two sequential tiers. The fast tier runs first and handles the immediate popup decision. The deep tier runs in the background and produces the detailed report.

#### Fast Tier (every main-frame navigation)
- Intercepts navigation via `declarativeNetRequest` → redirects to an extension-hosted interstitial page
- Runs: blocklist API lookups (priority order below) + whitelist check + URL pattern heuristics (lookalike characters, suspicious TLDs, IP-as-domain, brand impersonation)
- Uses SHA256(URL) hash as cache key — shared cache across all users on the server
- Target: < 1–2 seconds
- Result: **Safe** (page loads, logged quietly) or **Might be suspicious** (warning popup shown, user chooses next action)

**Blocklist API — Priority Order & Majority Vote**

APIs are called in priority order. Verdict is decided by majority (3 or more agree). VirusTotal is only called as a tiebreaker when the first four split 2–2.

| Priority | API | Free Tier Limits | Notes |
|----------|-----|-----------------|-------|
| 1st | Google Safe Browsing | Free, default quota via Developer Console (non-commercial) | Fastest, broadest coverage — first check always |
| 2nd | PhishTank (Cisco Talos) | Free with API key, rate limited per hour | Phishing-specific database, community-verified. For high volume: download their hourly database locally instead of live API calls |
| 3rd | Cloudflare | 1,200 requests / 5 minutes | Strong domain reputation, generous limits |
| 4th | Spamhaus | 5,000 queries/month free (Developer License), commercial from $5,000/year | Deep domain/IP reputation, strong on spam-origin infrastructure |
| 5th | VirusTotal | 500 requests/day, 4 requests/minute (non-commercial only) | Most comprehensive — reserved as tiebreaker only to protect quota |

**Majority vote logic:**
```
Checks 1-4 run in order
  - 3 or 4 agree (safe or suspicious) -> verdict decided, VirusTotal skipped
  - 2-2 split -> VirusTotal called as tiebreaker
```

**Commercial use note:** Google Safe Browsing and VirusTotal free tiers are non-commercial only. Upgrade required before any monetized public release.

**URL Pattern Heuristics — What the Fast Tier Checks**

Pure string/pattern analysis — no network call needed, near-instant:

| Pattern | Example | Why suspicious |
|---------|---------|---------------|
| Lookalike characters | `paypa1.com`, `arnazon.com` | Swaps letters/numbers to mimic real brands |
| Brand name in subdomain or path | `paypal.secure-login.com` | Real brand is not the actual domain |
| Hyphenated brand names | `pay-pal-login.com` | Common phishing pattern |
| IP address as domain | `http://192.168.1.1/login` | Legitimate services don't use raw IPs |
| Suspicious TLDs | `.xyz`, `.top`, `.click`, `.gq`, `.tk` | Frequently used for throwaway phishing domains |
| Excessive subdomains | `login.verify.secure.paypal.com.evil.ru` | Real domain is `evil.ru`, not PayPal |
| URL-encoded characters | `%70%61%79%70%61%6C.com` | Encoding tricks to hide the real URL |
| Overly long URLs | URLs > 100 characters with many parameters | Phishing links often hide destination in long query strings |
| Mismatched HTTPS | `http://` on a page asking for credentials | Legitimate login pages always use HTTPS |
| Known phishing keywords in URL | `verify`, `secure`, `update`, `confirm`, `login`, `account-suspended` combined with a brand name | Common in phishing URL patterns |

#### Deep Tier (user-triggered only — runs when user clicks "Deep Scan")
Runs all of the following in parallel on the server:

| Tool | What it checks |
|------|---------------|
| WHOIS analysis | Domain age, registration date, registrar, privacy protection |
| DNS verification | Record consistency, nameserver anomalies |
| NLP on page text | Urgency language, brand-domain mismatch, credential harvesting context, generic greetings (handled separately by developer) |
| Redirect & connection tracking | Full redirect chain (2 hops max on unknown domains), cross-domain resource loading, form submission target |
| DOM / source analysis | Login forms, hidden fields, password/OTP/SSN input patterns |
| Network traffic (recursive) | Unknown connected domains are fast-tier scanned up to 2 hops — results saved as structured JSON |

All tools output structured JSON and save their results. **The System LLM is not built in V1** — it will be plugged in later to read the saved JSON outputs and generate the plain-English description. V1 report panel shows the raw structured output from each tool directly.

**NLP analysis** is being handled separately by the developer. Its output is saved as structured JSON alongside the other tools, ready for the LLM to consume in a later version.

---

## 3. Navigation Flow

```
User clicks a link
       ↓
Intercepted → interstitial page
       ↓
Fast tier check (~0.5-2s)
  - Cache hit?  -> instant result
  - Cache miss? -> server checks blocklists + URL patterns
       ↓
  [Safe]                        [Might be suspicious]
     |                                   |
Page loads normally          Warning popup shown
Logged quietly               "This site might be suspicious"
                                        |
                ┌──────────────┼──────────────┐
           [Continue]      [Deep Scan]      [Go Back]
               |                |               |
         Page opens       Page opens      Nothing opens
         No scan          + Deep scan     User returns
         Log entry only   runs on server  No scan
                          + JSON saved    No log entry
                          + Report ready
```

**Scope:** Main-frame navigation only. Sub-resources (scripts, images, iframes) are not checked individually — this keeps check volume manageable and covers the actual threat model (the page the user is about to interact with).

---

## 4. Features

### 4.1 Warning Popup

Appears immediately when the fast tier flags a URL.

- Message: *"This site might be suspicious."*
- Shows: URL flagged, gentle warning — no strong claim
- Three actions:

**Continue** — page opens immediately, no scan runs, only a log entry is created. User proceeds at their own discretion.

**Deep Scan** — page opens AND the deep scan runs on the server. All tool outputs (WHOIS, DNS, DOM, NLP, network traffic) are saved as structured JSON. Report panel becomes available when the scan finishes.

**Go Back** — page does not open, user returns to where they were. No scan, no log entry.

- Additional button in popup (always visible):

**Open Dashboard** — opens the extension dashboard in a new browser tab. Dashboard covers API key settings and full deep scan results history.

### 4.2 Full Report Panel
- Separate page/panel, accessible after user clicks Deep Scan and scan completes
- Also accessible from the extension icon for any recently deep-scanned site
- **V1 contents:** Structured output from each tool displayed directly — one section per tool (WHOIS, DNS, DOM, NLP, redirect chain, network traffic)
- **After LLM is added:** A plain-English description of what the site is doing will appear at the top, generated by the System LLM reading the saved JSON outputs
- No verdict, no risk level, no "this is phishing" conclusion in either version

### 4.3 Notes
- Triggered when user clicks **Continue** or **Deep Scan** on a warning popup (not on Go Back)
- Optional — user can skip
- Short free-text field: "Why are you proceeding to this site?"
- Note is saved with the log entry for that URL

### 4.4 Logs
- **Scope:** Every site visited (phishing, safe, and sensitive)
- **Storage:** `chrome.storage.local` (local only in V1; Google Drive sync added in V2)
- **Format per entry:**

| Field | Value |
|-------|-------|
| Date & time | ISO timestamp |
| Source | Where the link came from (email, search, direct, ad, etc.) |
| URL | Full URL visited |
| Time spent | Duration on the page |
| Fast-tier flag | Flagged as suspicious / Passed clean |
| Deep scan run | Yes / No (did user click Deep Scan?) |
| Deep scan outputs | Saved JSON from all tools (if deep scan was run) |
| User action | Continue / Deep Scan / Go Back / No prompt |
| Note | User's note if added |

- **Exclusion list:** User can add domains they don't want logged (e.g. `mybank.com`). Domain-level — covers all pages under that domain. Stored in `chrome.storage.local`.

---

## 5. Whitelist

- **Type:** Developer-maintained shared list (major banks, top brands, top 1000 domains, known-good services)
- **Verification details stored per entry:** real SSL issuer, registrar, approximate registration age — used to compare against lookalikes
- **Distribution:** Fetched from server, cached locally in the extension (periodic refresh)
- **User contribution:** Not available in V1 (no auth). Users manage their own exclusion list separately.

---

## 6. Data & Privacy

| Data | Where it lives |
|------|---------------|
| User logs, notes, exclusion list | `chrome.storage.local` — never leaves the device in V1 |
| URL cache on server | SHA256(URL) hash as key — no plaintext browsing history stored server-side |
| Whitelist | Fetched from server, cached locally |
| Browsing data sent to server | URL (raw, for cache-miss scans only) + source tag |

**Privacy policy and Terms of Service** required before any public release (V1 prerequisite, not a build task).

---

## 7. Server Architecture

- Developer-run SaaS backend
- Responsibilities: fast-tier checks, deep-tier scans, saving tool outputs as JSON, shared URL cache, whitelist serving
- **Caching strategy:** First user to hit a URL triggers the full scan. All subsequent users get the cached verdict instantly. Cache key = SHA256(URL). Particularly effective against phishing campaigns (same URL blasted to many users).
- **Rate limiting in V1:** IP-based (user accounts not available until V2)
- **No user data stored server-side in V1**

---

## 8. V1 Scope (Build First)

✅ Fast tier — blocklist APIs (priority order + majority vote) + URL pattern heuristics
✅ Warning popup — Continue (log only) or Deep Scan (scan + report)
✅ Deep scan — WHOIS, DNS, DOM, redirect chain, network traffic (all save structured JSON)
✅ NLP analysis — developer-handled separately, output saved as JSON
✅ Report panel — structured JSON output per tool (V1, no LLM yet)
✅ Notes on Continue or Deep Scan
✅ Full browsing log (local, no risk level field)
✅ Exclusion list
✅ Developer-maintained whitelist
✅ Shared URL hash cache on server
✅ Extension dashboard (new browser tab) — API key status + deep scan results history
✅ Popup "Open Dashboard" button
✅ API keys stored server-side (developer-managed, users need no setup)
✅ Error handling — full system coverage (see Section 11)
⏳ System LLM — deferred, plugged in after rest is built

---

## 9. V2 Roadmap (After V1 Works)

- User authentication (Google OAuth)
- Google Drive sync for logs
- Per-user rate limiting and usage tiers
- User-contributed whitelist entries (with verification)
- **System LLM** — plug into saved JSON outputs to generate plain-English behavioral descriptions in the report panel
- API cost optimization (tiered LLM usage, cheaper models for low-confidence cases)
- **Site behavior analysis** — sandboxed headless browser (Puppeteer/Playwright) on server to observe live popups, auto-downloads, and redirect behavior
- Privacy Policy and ToS (required before public launch)
- Upgrade Google Safe Browsing to Google Web Risk (commercial) and VirusTotal to paid plan before monetization
- Advanced "bring your own API key" option — power users can optionally enter their own API keys for any of the 5 blocklist services, bypassing the server's shared keys and using their own quota

---

## 10. Open Technical Notes

- **Manifest V3 constraint:** True packet-level network inspection is not available to Chrome extensions. "Network analysis" is implemented as redirect chain tracking (`chrome.webNavigation`) + connected domain monitoring (`chrome.webRequest` in observe mode) + form submission target from DOM analysis. Payload content of HTTPS requests is not visible — destination domain is sufficient for detection purposes.
- **Network traffic — recursive scanning:** Unknown connected domains discovered during deep tier analysis are run through the fast-tier scan, up to 2 hops. Whitelist/cache hits are skipped. Results saved as structured JSON alongside other tool outputs. Hop limit is expandable in future versions.
- **Site behavior analysis (popups, live redirection observation):** Deferred to V2/V3. Requires a sandboxed headless browser (Puppeteer/Playwright in a throwaway container) on the server. V1 uses DOM/source analysis to infer likely behavior from code instead of live observation.
- **DOM analysis timing:** Because the page is paused before loading, DOM/source analysis in the deep tier fetches the page HTML via a background server-side request (not from the live tab).
- **System LLM — deferred:** Not built in V1. All tool outputs are saved as structured JSON so the LLM can be plugged in later with a single connection point. When added, it reads the saved JSON and produces a plain-English behavioral description — no verdict, no risk level, no confidence score.
- **NLP in V1:** Handled separately by the developer. Output saved as structured JSON alongside other tool outputs, ready for LLM consumption later.
- **Drive sync dependency:** Requires Google OAuth, which is a V2 feature. Local storage only in V1.

---

## 11. Error Handling

Error handling covers the full system — every component has a defined failure behavior. The guiding principle: **fail safe** (when in doubt, treat as suspicious rather than letting through).

### Fast Tier — Blocklist APIs
| Scenario | Behavior |
|----------|----------|
| One API times out or errors | Skip it, continue with remaining APIs — majority vote still applies to available results |
| All APIs fail or time out | Treat URL as suspicious — show warning popup, do not silently pass through |
| Cache server unreachable | Bypass cache, run fresh check. If that also fails, treat as suspicious |
| Rate limit hit on an API | Skip that API for this request, log the rate limit event server-side for monitoring |

### Deep Scan — Individual Tools
| Scenario | Behavior |
|----------|----------|
| WHOIS lookup fails | Save error state in JSON (`"whois": {"status": "error", "reason": "timeout"}`), continue with other tools |
| DNS lookup fails | Same — error state saved, scan continues |
| DOM fetch fails (server can't retrieve page HTML) | Save error state, note in report that DOM analysis was unavailable |
| NLP analysis fails | Save error state, continue with other tools |
| Network traffic recursive scan fails | Save partial results if any hops succeeded, error state for failed ones |
| All deep scan tools fail | Report panel shows: scan attempted but all tools failed — raw error states saved in JSON |

### Extension → Server Communication
| Scenario | Behavior |
|----------|----------|
| Server unreachable (user is offline) | Show message in popup: "Could not check this site — no connection to scan server." Give user Continue or Go Back — no silent pass-through |
| Server returns unexpected response format | Treat as suspicious, log malformed response for debugging |
| Request times out | After configurable timeout (e.g. 5s), treat as suspicious |

### Storage
| Scenario | Behavior |
|----------|----------|
| `chrome.storage.local` write fails | Log error to console, attempt retry once — if still fails, skip that log entry rather than crashing |
| Storage quota exceeded | Alert user that log storage is full, prompt to clear old entries |

### General Principle
All errors are logged server-side (for APIs and deep scan tools) or to the extension console (for local storage). No error should ever silently pass a URL through as safe — when the system can't make a determination, it defaults to "might be suspicious."
