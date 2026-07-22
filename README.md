# PhishGuard — Phishing Detection Chrome Extension

A real-time phishing detection system built as a Chrome extension backed by a local Python desktop application. When you navigate to a URL, PhishGuard checks it against multiple blocklist APIs and URL heuristics, warns you if something looks suspicious, and gives you a detailed deep scan report on demand.

---

## How It Works

Every URL you visit goes through two stages:

**Fast Tier (every navigation, < 2 seconds)**
Checks against Google Safe Browsing, PhishTank, Cloudflare, Spamhaus, and VirusTotal (as tiebreaker), plus URL pattern heuristics. If anything looks suspicious, a warning popup appears.

**Deep Tier (user-triggered)**
On the warning popup, clicking Deep Scan runs a full analysis — WHOIS lookup, DNS verification, DOM and source code analysis, redirect chain tracking, and network traffic analysis. All results saved locally and viewable in the desktop app.

---

## Requirements

| Tool | Version | Download |
|------|---------|----------|
| Windows | 10 or 11 | — |
| Python | 3.11+ | https://python.org |
| Google Chrome | Latest | https://chrome.google.com |
| Git | Latest | https://git-scm.com |

---

## Installation

### Step 1 — Clone the Repository

```bash
git clone https://github.com/ibondforger-bit/detecting_phishing.git
cd detecting_phishing
```

### Step 2 — Run the Setup Script

Right-click `setup.ps1` and select **Run with PowerShell**.

Or run it from terminal:

```powershell
powershell -ExecutionPolicy Bypass -File setup.ps1
```

The script will automatically:
- Create a Python virtual environment
- Install all dependencies from `requirements.txt`
- Create the required folder structure (`/data/cache/`, `/data/logs/`, `/data/outputs/`)
- Create initial `settings.json` and `user_whitelist.json`
- Launch the desktop app

### Step 3 — Complete the Setup Wizard

On first launch, the setup wizard will guide you through:

1. **API Keys (optional)** — enter any API keys you have. The system works without them using URL heuristics only. Keys are stored securely in Windows Credential Manager — never in files.
2. **Auto-Start** — choose whether PhishGuard starts automatically with Windows
3. **Chrome Extension** — follow the link to install the extension

### Step 4 — Load the Chrome Extension

1. Open Chrome and go to `chrome://extensions/`
2. Enable **Developer Mode** (top-right toggle)
3. Click **Load unpacked**
4. Select the `/extension/` folder from the cloned repo
5. The PhishGuard icon will appear in your Chrome toolbar

---

## API Keys (Optional)

PhishGuard works without API keys using URL pattern heuristics. For stronger protection, you can add keys for any of these services:

| API | Free Tier | Get Key |
|-----|----------|---------|
| Google Safe Browsing | Free (non-commercial) | https://developers.google.com/safe-browsing |
| PhishTank | Free with registration | https://www.phishtank.com/api_register.php |
| Cloudflare | 1,200 requests / 5 min | https://developers.cloudflare.com |
| Spamhaus | 5,000 queries/month free | https://www.spamhaus.com |
| VirusTotal | 500 requests/day (non-commercial) | https://www.virustotal.com/gui/join-us |

Enter keys anytime via **Open Dashboard** in the extension popup → Settings.

> **Note:** Google Safe Browsing and VirusTotal free tiers are for non-commercial use only.

---

## Usage

**Normal browsing:** PhishGuard runs silently in the background. If a site looks suspicious, a warning popup appears automatically.

**Warning popup options:**
- **Continue** — opens the site, logs the visit, no scan
- **Deep Scan** — opens the site and runs a full analysis, report available in desktop app
- **Go Back** — closes, returns to previous page

**Desktop app:** Click the PhishGuard system tray icon (bottom-right of Windows taskbar) to open the full app. View logs, reports, manage API keys, and whitelist settings.

**Extension popup:** Click the PhishGuard icon in Chrome toolbar to see connection status and open the dashboard.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Chrome Extension | Manifest V3, HTML, CSS, JavaScript |
| Desktop App | Python, PyQt6 |
| Backend | Python, FastAPI, REST API |
| Python Libraries | `python-whois`, `dnspython`, `httpx`, `BeautifulSoup`, `re` |
| Caching | `diskcache` |
| Task Queue | Celery |
| API Key Storage | `keyring` (Windows Credential Manager) |
| Data Format | JSON |

---

## Troubleshooting

**Extension shows "The server is not working"**
→ The desktop app is not running. Open PhishGuard from the Start Menu or run `python gui.py`.

**Extension shows "Protection is paused"**
→ You stopped the backend in the desktop app. Click Start in the desktop app to resume.

**Setup script blocked by Windows**
→ Run PowerShell as Administrator and try again, or right-click `setup.ps1` → Properties → Unblock.

**Port already in use**
→ The desktop app will automatically try ports 5000 → 5001 → 5002 → 5003. If all are in use, close other applications using those ports.

---

## Roadmap
### V2.0.0
- [ ] PyQt6 desktop application
- [ ] Local backend (no remote server)
- [ ] System tray integration
- [ ] Auto-start with Windows
- [ ] Manual URL scan in desktop app
- [ ] Whitelist management in desktop app
- [ ] Basic stats dashboard
- [ ] PowerShell auto-setup

### Future
- [ ] System LLM — plain-English behavioral description
- [ ] Log export (CSV / PDF)
- [ ] Windows native notifications
- [ ] Multi-browser support (Edge, Firefox)
- [ ] Mac / Linux support

---

## License

MIT License — see `LICENSE` file for details.

---

## Author

[@ibondforger-bit](https://github.com/ibondforger-bit)
