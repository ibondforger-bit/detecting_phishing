const INTERSTITIAL = chrome.runtime.getURL("interstitial.html");
const INTERNAL_PROTOCOLS = ["chrome:", "chrome-extension:", "edge:", "about:", "devtools:"];
const bypassTabs = new Map();

let protectionStatus = "running"; // "running", "paused", "error"

chrome.runtime.onInstalled.addListener(async () => {
  await probeBackend();
  await checkHealth();
  chrome.alarms.create("healthCheckAlarm", { periodInMinutes: 1 });
});

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name === "healthCheckAlarm") {
    await checkHealth();
  }
});

// Initial run
probeBackend().then(checkHealth);

// In-memory active loop
setInterval(checkHealth, 30000);

chrome.webNavigation.onBeforeNavigate.addListener(async (details) => {
  if (details.frameId !== 0 || !details.url) return;
  const url = new URL(details.url);
  if (INTERNAL_PROTOCOLS.includes(url.protocol)) return;
  if (details.url.startsWith(INTERSTITIAL)) return;

  const data = await chrome.storage.local.get({ protectionStatus: "running" });
  if (data.protectionStatus !== "running") {
    return;
  }

  const bypassUrl = bypassTabs.get(details.tabId);
  if (bypassUrl === details.url) {
    bypassTabs.delete(details.tabId);
    return;
  }

  const excluded = await isExcluded(url.hostname);
  if (excluded) return;

  const target = `${INTERSTITIAL}?tabId=${details.tabId}&url=${encodeURIComponent(details.url)}`;
  chrome.tabs.update(details.tabId, { url: target });
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  handleMessage(message, sender).then(sendResponse).catch((error) => sendResponse({ ok: false, error: String(error) }));
  return true;
});

async function handleMessage(message) {
  if (message.type === "continue_to_url") {
    bypassTabs.set(message.tabId, message.url);
    await chrome.tabs.update(message.tabId, { url: message.url });
    return { ok: true };
  }
  if (message.type === "open_dashboard") {
    await chrome.tabs.create({ url: chrome.runtime.getURL("dashboard.html") });
    return { ok: true };
  }
  if (message.type === "open_report") {
    await chrome.tabs.create({ url: chrome.runtime.getURL(`report.html?scanId=${encodeURIComponent(message.scanId)}`) });
    return { ok: true };
  }
  if (message.type === "get_status") {
    await checkHealth();
    return { ok: true, status: protectionStatus };
  }
  return { ok: false, error: "unknown message" };
}

async function isExcluded(hostname) {
  const { exclusionList = [] } = await chrome.storage.local.get({ exclusionList: [] });
  const host = hostname.replace(/^www\./, "");
  return exclusionList.some((domain) => host === domain || host.endsWith(`.${domain}`));
}

async function probeBackend() {
  const ports = [5000, 5001, 5002, 5003];
  for (const port of ports) {
    try {
      const controller = new AbortController();
      const id = setTimeout(() => controller.abort(), 1000);
      const resp = await fetch(`http://127.0.0.1:${port}/health`, { signal: controller.signal });
      clearTimeout(id);
      if (resp.ok) {
        const body = await resp.json();
        if (body.status === "running" || body.status === "paused") {
          const url = `http://127.0.0.1:${port}`;
          await chrome.storage.local.set({ serverUrl: url });
          return url;
        }
      }
    } catch (e) {
      // ignore
    }
  }
  return null;
}

async function checkHealth() {
  let serverUrl = "";
  try {
    const data = await chrome.storage.local.get({ serverUrl: "http://127.0.0.1:5000" });
    serverUrl = data.serverUrl;
    
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), 1500);
    const resp = await fetch(`${serverUrl}/health`, { signal: controller.signal });
    clearTimeout(id);
    
    if (resp.ok) {
      const body = await resp.json();
      protectionStatus = body.status;
    } else {
      protectionStatus = "error";
    }
  } catch (e) {
    console.log("WebSense: Health check failed, probing...");
    const newUrl = await probeBackend();
    if (newUrl) {
      try {
        const resp = await fetch(`${newUrl}/health`);
        const body = await resp.json();
        protectionStatus = body.status;
      } catch (e2) {
        protectionStatus = "error";
      }
    } else {
      protectionStatus = "error";
    }
  }
  await chrome.storage.local.set({ protectionStatus });
}

