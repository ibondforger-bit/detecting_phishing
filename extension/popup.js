async function updatePopupStatus() {
  const data = await chrome.storage.local.get({ protectionStatus: "error" });
  const status = data.protectionStatus;
  
  const statusDot = document.getElementById("status-dot");
  const statusText = document.getElementById("status-text");
  
  if (status === "running") {
    statusDot.style.backgroundColor = "#10b981"; // green
    statusText.textContent = "Active & Protected";
    statusText.style.color = "#10b981";
  } else if (status === "paused") {
    statusDot.style.backgroundColor = "#f59e0b"; // yellow
    statusText.textContent = "Protection is paused";
    statusText.style.color = "#f59e0b";
  } else {
    statusDot.style.backgroundColor = "#ef4444"; // red
    statusText.textContent = "The server is not working";
    statusText.style.color = "#ef4444";
  }
}

document.getElementById("dashboard").addEventListener("click", () => {
  chrome.runtime.sendMessage({ type: "open_dashboard" });
});

document.getElementById("report").addEventListener("click", async () => {
  const { lastScanId } = await chrome.storage.local.get("lastScanId");
  if (lastScanId) {
    chrome.runtime.sendMessage({ type: "open_report", scanId: lastScanId });
  }
});

// Update immediately, and request status check
chrome.runtime.sendMessage({ type: "get_status" }).then((response) => {
  if (response && response.status) {
    chrome.storage.local.set({ protectionStatus: response.status }).then(updatePopupStatus);
  } else {
    updatePopupStatus();
  }
}).catch(() => {
  updatePopupStatus();
});

