const serverInput = document.getElementById("server-url");
const history = document.getElementById("history");
const exclusions = document.getElementById("exclusions");
const exclusionInput = document.getElementById("exclusion-input");

const apiForm = document.getElementById("api-keys-form");
const apiStatusMsg = document.getElementById("api-status-msg");

const googleInput = document.getElementById("google-safe-browsing-key");

document.getElementById("save-server").addEventListener("click", async () => {
  await chrome.storage.local.set({ serverUrl: serverInput.value.trim() });
  await refresh();
});

document.getElementById("add-exclusion").addEventListener("click", async () => {
  const domain = exclusionInput.value.trim().replace(/^https?:\/\//, "").split("/")[0].replace(/^www\./, "");
  if (!domain) return;
  const { exclusionList = [] } = await chrome.storage.local.get({ exclusionList: [] });
  await chrome.storage.local.set({ exclusionList: Array.from(new Set([...exclusionList, domain])) });
  exclusionInput.value = "";
  await renderExclusions();
});

apiForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  apiStatusMsg.textContent = "Saving...";
  apiStatusMsg.className = "";
  
  const { serverUrl } = await chrome.storage.local.get({ serverUrl: "http://127.0.0.1:8000" });
  
  const payload = {};
  if (googleInput.value) payload.google_safe_browsing_api_key = googleInput.value.trim();
  
  try {
    const response = await fetch(`${serverUrl}/api-keys`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    
    if (response.ok) {
      apiStatusMsg.textContent = "API keys updated successfully!";
      apiStatusMsg.className = "ok";
      googleInput.value = "";
      await refresh();
    } else {
      const err = await response.json();
      apiStatusMsg.textContent = `Error: ${err.detail || response.statusText}`;
      apiStatusMsg.className = "bad";
    }
  } catch (error) {
    apiStatusMsg.textContent = `Failed to contact server: ${error.message}`;
    apiStatusMsg.className = "bad";
  }
});

refresh();

async function refresh() {
  const { serverUrl } = await chrome.storage.local.get({ serverUrl: "http://127.0.0.1:8000" });
  serverInput.value = serverUrl;
  await Promise.all([renderApiStatus(serverUrl), renderHistory(serverUrl), renderExclusions()]);
}

async function renderApiStatus(serverUrl) {
  try {
    const response = await fetch(`${serverUrl}/api-status`);
    if (!response.ok) throw new Error(response.statusText);
    const data = await response.json();
    
    googleInput.placeholder = data.google_safe_browsing?.active ? "•••••••• (Configured)" : "Not configured";
  } catch (error) {
    googleInput.placeholder = "Server unavailable";
  }
}

async function renderHistory(serverUrl) {
  history.textContent = "Loading...";
  try {
    const response = await fetch(`${serverUrl}/reports`);
    const reports = await response.json();
    history.innerHTML = "";
    if (!reports.length) {
      history.textContent = "No scans have been run yet.";
      return;
    }
    for (const report of reports) {
      const button = document.createElement("button");
      button.textContent = `${report.created_at} - ${report.url}`;
      button.addEventListener("click", () => chrome.runtime.sendMessage({ type: "open_report", scanId: report.scan_id }));
      history.appendChild(button);
    }
  } catch (error) {
    history.textContent = "Could not load scan history.";
  }
}

async function renderExclusions() {
  const { exclusionList = [] } = await chrome.storage.local.get({ exclusionList: [] });
  exclusions.innerHTML = "";
  if (!exclusionList.length) {
    exclusions.textContent = "No excluded domains.";
    return;
  }
  for (const domain of exclusionList) {
    const row = document.createElement("div");
    row.className = "panel";
    row.innerHTML = `<strong>${domain}</strong> <button>Remove</button>`;
    row.querySelector("button").addEventListener("click", async () => {
      await chrome.storage.local.set({ exclusionList: exclusionList.filter((item) => item !== domain) });
      await renderExclusions();
    });
    exclusions.appendChild(row);
  }
}
