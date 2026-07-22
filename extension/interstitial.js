const params = new URLSearchParams(location.search);
const tabId = Number(params.get("tabId"));
const targetUrl = params.get("url");

const els = {
  checking: document.getElementById("checking"),
  warning: document.getElementById("warning"),
  offline: document.getElementById("offline"),
  checkingUrl: document.getElementById("checking-url"),
  warningUrl: document.getElementById("warning-url"),
  offlineUrl: document.getElementById("offline-url"),
  warningReason: document.getElementById("warning-reason"),
  note: document.getElementById("note")
};

document.getElementById("continue").addEventListener("click", () => continueToUrl("Continue", false));
document.getElementById("deep-scan").addEventListener("click", () => continueToUrl("Deep Scan", true));
document.getElementById("go-back").addEventListener("click", goBack);
document.getElementById("dashboard").addEventListener("click", openDashboard);
document.getElementById("offline-continue").addEventListener("click", () => continueToUrl("Continue", false));
document.getElementById("offline-back").addEventListener("click", goBack);
document.getElementById("offline-dashboard").addEventListener("click", openDashboard);

let lastCheckResult = null;

init();

async function init() {
  els.checkingUrl.textContent = targetUrl;
  els.warningUrl.textContent = targetUrl;
  els.offlineUrl.textContent = targetUrl;

  try {
    const result = await fastCheck(targetUrl);
    lastCheckResult = result;
    if (result.result === "safe") {
      await saveLog("No prompt", result, false, "");
      await goToTarget();
      return;
    }
    showWarning(result.reason || "Fast tier found suspicious signals.");
  } catch (error) {
    showOffline();
  }
}

async function fastCheck(url) {
  const { serverUrl } = await chrome.storage.local.get({ serverUrl: "http://127.0.0.1:5000" });
  const urlHash = await sha256(url);
  let response = await fetch(`${serverUrl}/check`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url_hash: urlHash, source: "browser" })
  });
  if (response.status === 404) {
    response = await fetch(`${serverUrl}/check`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url_hash: urlHash, url, source: "browser" })
    });
  }
  if (!response.ok) throw new Error(`Check failed: ${response.status}`);
  return response.json();
}

async function continueToUrl(action, runDeepScan) {
  let scanId = null;
  if (runDeepScan) {
    scanId = await startDeepScan();
    await chrome.storage.local.set({ lastScanId: scanId });
  }
  
  // Use lastCheckResult instead of dummy object to preserve details/APIs list
  const checkRes = lastCheckResult || { result: "suspicious", reason: "Bypassed warning", details: {} };
  await saveLog(action, checkRes, runDeepScan, els.note.value.trim(), scanId);
  await goToTarget();
}

async function startDeepScan() {
  const { serverUrl } = await chrome.storage.local.get({ serverUrl: "http://127.0.0.1:5000" });
  const response = await fetch(`${serverUrl}/deepscan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url: targetUrl, source: "browser" })
  });
  if (!response.ok) throw new Error(`Deep scan failed: ${response.status}`);
  const body = await response.json();
  return body.scan_id;
}

async function saveLog(action, checkResult, deepScanRun, note, scanId = null) {
  const { visitLogs = [] } = await chrome.storage.local.get({ visitLogs: [] });
  const logItem = {
    timestamp: new Date().toISOString(),
    source: "browser",
    url: targetUrl,
    timeSpent: null,
    fastTierFlag: checkResult.result === "suspicious" ? "Flagged as suspicious" : "Passed clean",
    deepScanRun,
    userAction: action,
    note: note || null,
    scanId,
    details: checkResult.details || null
  };
  
  visitLogs.push(logItem);
  await chrome.storage.local.set({ visitLogs: visitLogs.slice(-1000) });

  // Send to backend logs endpoint
  try {
    const { serverUrl } = await chrome.storage.local.get({ serverUrl: "http://127.0.0.1:5000" });
    await fetch(`${serverUrl}/logs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(logItem)
    });
  } catch (error) {
    console.error("Failed to POST log to server:", error);
  }
}

async function goToTarget() {
  await chrome.runtime.sendMessage({ type: "continue_to_url", tabId, url: targetUrl });
}

function goBack() {
  history.length > 1 ? history.back() : chrome.tabs.remove(tabId);
}

function openDashboard() {
  chrome.runtime.sendMessage({ type: "open_dashboard" });
}

function showWarning(reason) {
  els.checking.classList.add("hidden");
  els.offline.classList.add("hidden");
  els.warning.classList.remove("hidden");
  els.warningReason.textContent = reason;
}

function showOffline() {
  els.checking.classList.add("hidden");
  els.warning.classList.add("hidden");
  els.offline.classList.remove("hidden");
}

async function sha256(text) {
  const bytes = new TextEncoder().encode(text);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest)).map((byte) => byte.toString(16).padStart(2, "0")).join("");
}
