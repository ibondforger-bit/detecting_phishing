# PhishGuard — Project Structure Setup Guide
*V2.0.0 | Windows | Python + PyQt6 + Chrome Extension*

---

## Final Project Structure

```
/phishing-extension/
│
├── gui.py                          # Entry point — PyQt6 desktop app & setup wizard
├── requirements.txt                # Python dependencies
├── start.bat                       # Starts gui.py
├── .env                            # Non-sensitive config only (port, timeout, etc.)
├── .env.example                    # Template for .env — safe to commit
├── .gitignore
├── README.md
│
├── /docs/                          # All documentation
│   ├── phishing_extension_plan.md
│   ├── workflow.md
│   ├── update.md
│   └── project_structure_setup.md  # This file
│
├── /data/                          # All runtime-generated data (gitignored)
│   ├── .gitkeep                    # Keeps /data/ tracked in Git, contents ignored
│   ├── settings.json               # App state (first_launch, active port, etc.)
│   ├── /cache/                     # diskcache SQLite files
│   │   ├── .gitkeep
│   │   ├── cache.db
│   │   ├── cache.db-shm
│   │   └── cache.db-wal
│   ├── /logs/                      # Browsing log
│   │   ├── .gitkeep
│   │   └── browsing_log.json
│   └── /outputs/                   # Deep scan JSON results
│       ├── .gitkeep
│       └── [scan_id].json
│
├── /whitelist/                     # Whitelist definitions
│   ├── whitelist_fast.json         # Base fast lookup list (pre-loaded)
│   ├── whitelist_details.json      # Full verification details (deep scan use)
│   └── user_whitelist.json         # User-added custom trusted domains
│
├── /extension/                     # Chrome Extension source files
│   ├── manifest.json
│   ├── background.js
│   ├── interstitial.html
│   ├── interstitial.js
│   ├── popup.html
│   ├── popup.js
│   ├── dashboard.html
│   ├── dashboard.js
│   ├── report.html
│   ├── report.js
│   └── styles.css
│
└── /server/                        # FastAPI backend
    ├── __init__.py
    ├── main.py                     # App entry, lifespan, router registration
    ├── config.py                   # keyring read/write for API keys
    ├── models.py                   # Pydantic schemas
    │
    ├── /routers/
    │   ├── __init__.py
    │   ├── fast_tier.py            # /check, /logs
    │   ├── deep_scan.py            # /deepscan, /reports
    │   └── whitelist.py            # /whitelist
    │
    ├── /tools/
    │   ├── __init__.py
    │   ├── blocklists.py           # All 5 APIs — independent, names flagging API
    │   ├── whois_tool.py
    │   ├── dns_tool.py
    │   ├── dom_tool.py
    │   ├── redirect_tool.py
    │   ├── network_tool.py
    │   ├── url_heuristics.py
    │   └── nlp_tool.py             # Placeholder — returns empty JSON stub
    │
    └── /cache/
        ├── __init__.py
        └── cache_client.py         # diskcache wrapper
```

---

## Step 0 — Clean Up Old Structure

Before creating anything new, remove all files and folders that are no longer needed in V2. Do this first — in the exact order below — to avoid confusion during restructuring.

> ⚠️ **Before deleting anything:** make sure your code is committed to Git so you can recover anything if needed.
> ```bash
> git add .
> git commit -m "snapshot before V2 restructure"
> ```

---

### 0.1 — Files & Folders to Delete

Run these commands from the project root:

```bash
# Remove server templates folder (setup.html replaced by gui.py wizard)
rmdir /s /q server\templates

# Remove old redis_client.py (replaced by cache_client.py)
del server\cache\redis_client.py

# Remove root-level cache folder (moving to /data/cache/)
rmdir /s /q cache

# Remove root-level logs folder (moving to /data/logs/)
rmdir /s /q logs

# Remove root-level outputs folder (moving to /data/outputs/)
rmdir /s /q outputs

# Remove settings.json from root (moving to /data/settings.json)
del settings.json

# Remove __pycache__ from root (auto-generated, never needed)
rmdir /s /q __pycache__
```

---

### 0.2 — Files to Move (Not Delete)

These files are still needed — just in a new location:

| Current location | Move to | Command |
|-----------------|---------|---------|
| `phishing_extension_plan.md` (root) | `/docs/` | `move phishing_extension_plan.md docs\` |
| `workflow.md` (root) | `/docs/` | `move workflow.md docs\` |
| `update.md` (root) | `/docs/` | `move update.md docs\` |

Run these after creating the `/docs/` folder in Step 3.

---

### 0.3 — Verify Clean State

After deleting, your root should contain only these items:

```
/phishing-extension/
├── .env
├── .env.example
├── .gitignore
├── gui.py
├── README.md
├── requirements.txt
├── start.bat
├── /extension/
├── /server/         ← templates/ removed, redis_client.py removed
└── /whitelist/
```

If anything unexpected is still there, remove it before moving to Step 1.

---

## Step 1 — Prerequisites

Before setting up, make sure the following are installed on your Windows machine:

| Tool | Version | Check Command |
|------|---------|---------------|
| Python | 3.11+ | `python --version` |
| Git | Latest | `git --version` |
| Google Chrome | Latest | Open Chrome → Settings → About |
| VS Code (recommended) | Latest | — |

---

## Step 2 — Clone or Create the Project

**If starting fresh:**
```bash
mkdir phishing-extension
cd phishing-extension
git init
```

**If cloning existing repo:**
```bash
git clone <repo-url>
cd phishing-extension
```

---

## Step 3 — Create the Full Folder Structure

Run this in the project root to create all folders and `.gitkeep` files:

```bash
# Create all folders
mkdir docs
mkdir data
mkdir data\cache
mkdir data\logs
mkdir data\outputs
mkdir whitelist
mkdir extension
mkdir server
mkdir server\routers
mkdir server\tools
mkdir server\cache

# Create .gitkeep files to track empty folders in Git
type nul > data\.gitkeep
type nul > data\cache\.gitkeep
type nul > data\logs\.gitkeep
type nul > data\outputs\.gitkeep
```

---

## Step 4 — Set Up Python Virtual Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate it
.venv\Scripts\activate

# Confirm it's active — you should see (.venv) in your terminal
```

> **Important:** Always activate the virtual environment before running anything.
> If you see `(.venv)` at the start of your terminal line, it's active.

---

## Step 5 — Install Python Dependencies

```bash
pip install -r requirements.txt
```

**Full `requirements.txt` contents:**
```
fastapi
uvicorn
python-whois
dnspython
httpx
beautifulsoup4
celery
diskcache
keyring
python-dotenv
pydantic
PyQt6
pyinstaller
```

---

## Step 6 — Set Up the `.env` File

Copy the example file:
```bash
copy .env.example .env
```

**`.env` contains non-sensitive config only — no API keys here (those go in Windows Credential Manager via keyring):**
```
SERVER_PORT=5000
SERVER_HOST=127.0.0.1
REQUEST_TIMEOUT=5
CACHE_EXPIRY_SECONDS=86400
DATA_DIR=./data
WHITELIST_DIR=./whitelist
OUTPUTS_DIR=./data/outputs
LOGS_FILE=./data/logs/browsing_log.json
```

---

## Step 7 — Set Up `.gitignore`

Create or update `.gitignore` to protect sensitive and runtime files:

```gitignore
# Virtual environment
.venv/

# Runtime data — all of it gitignored, only folder structure tracked
/data/*
!/data/.gitkeep
!/data/cache/.gitkeep
!/data/logs/.gitkeep
!/data/outputs/.gitkeep

# Environment file — never commit real .env
.env

# Python cache
__pycache__/
*.py[cod]
*.pyo

# VS Code
.vscode/

# PyInstaller build output
/build/
/dist/
*.spec
```

---

## Step 8 — Create Placeholder Files

### `server/tools/nlp_tool.py` (placeholder)
```python
# nlp_tool.py
# Placeholder — NLP analysis handled separately by developer
# Returns empty JSON stub so deep scan pipeline does not break

async def run_nlp_analysis(html_content: str) -> dict:
    return {
        "status": "not_implemented",
        "reason": "NLP analysis module not yet connected",
        "findings": []
    }
```

### `data/settings.json` (initial state)
```json
{
  "first_launch": true,
  "active_port": 5000,
  "auto_start": false,
  "setup_complete": false
}
```

### `whitelist/user_whitelist.json` (empty initial state)
```json
{
  "version": "1.0",
  "user_added_domains": []
}
```

---

## Step 9 — Load the Chrome Extension

1. Open Google Chrome
2. Go to `chrome://extensions/`
3. Enable **Developer Mode** (top-right toggle)
4. Click **Load unpacked**
5. Select the `/extension/` folder from your project
6. The PhishGuard extension icon should appear in your Chrome toolbar

---

## Step 10 — Run the Project

```bash
# Make sure virtual environment is active
.venv\Scripts\activate

# Start the desktop app (this starts everything — PyQt6 UI + FastAPI server)
python gui.py
```

Or double-click `start.bat` from Windows Explorer.

---

## Step 11 — Verify Everything is Working

| Check | How to verify |
|-------|--------------|
| Desktop app opens | PyQt6 window appears |
| Setup wizard shows on first launch | `settings.json` → `"first_launch": true` triggers wizard |
| FastAPI server running | Go to `http://127.0.0.1:5000/docs` in browser — FastAPI docs page loads |
| Extension connected | Extension icon in Chrome shows 🟢 green status |
| Health check working | Go to `http://127.0.0.1:5000/health` — returns `{"status": "running"}` |
| Cache working | Navigate to any site — check `/data/cache/` for `cache.db` file |
| Logs working | Navigate to any site — check `/data/logs/browsing_log.json` for entry |

---

## Folder Responsibilities — Quick Reference

| Folder / File | Who writes to it | Who reads from it |
|---------------|-----------------|-------------------|
| `/data/cache/` | `cache_client.py` | `fast_tier.py` |
| `/data/logs/` | `fast_tier.py` (via extension) | Desktop app logs section |
| `/data/outputs/` | `deep_scan.py` | Desktop app reports section, `report.js` |
| `/data/settings.json` | `gui.py` (setup wizard) | `gui.py` (on every launch) |
| `/whitelist/whitelist_fast.json` | Developer (manual update) | `whitelist.py`, extension JS Set |
| `/whitelist/whitelist_details.json` | Developer (manual update) | `whois_tool.py` (deep scan comparison) |
| `/whitelist/user_whitelist.json` | Desktop app whitelist manager | `whitelist.py` |
| `keyring` (Windows Credential Manager) | `config.py` (via setup wizard) | `blocklists.py` |

---

## What's Gitignored vs Tracked

| Item | Gitignored | Reason |
|------|-----------|--------|
| `/data/*` contents | ✅ Yes | Runtime data — different on every machine |
| `/data/.gitkeep` files | ❌ No | Keeps folder structure in repo |
| `.env` | ✅ Yes | Contains config — use `.env.example` instead |
| `.venv/` | ✅ Yes | Rebuilt via `pip install -r requirements.txt` |
| `__pycache__/` | ✅ Yes | Auto-generated, never commit |
| `/whitelist/*.json` | ❌ No | Source data — should be in repo |
| `/extension/` | ❌ No | Source code — must be in repo |
| `/server/` | ❌ No | Source code — must be in repo |
| `gui.py` | ❌ No | Entry point — must be in repo |
| `settings.json` | ✅ Yes (inside `/data/`) | Runtime state |

---

*Document version: V2.0.0 | Last updated: 2026-07-20*
