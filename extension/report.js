const scanId = new URLSearchParams(location.search).get("scanId");
const meta = document.getElementById("meta");
const tools = document.getElementById("tools");

load();

async function load() {
  const { serverUrl } = await chrome.storage.local.get({ serverUrl: "http://127.0.0.1:8000" });
  const response = await fetch(`${serverUrl}/reports/${encodeURIComponent(scanId)}`);
  if (!response.ok) {
    meta.textContent = "Report not found or server unavailable.";
    return;
  }
  const report = await response.json();
  meta.textContent = `${report.url} - ${report.created_at}`;
  tools.innerHTML = "";
  for (const [name, value] of Object.entries(report.tools || {})) {
    const section = document.createElement("section");
    section.className = "panel";
    section.innerHTML = `<h2>${label(name)}</h2><pre>${escapeHtml(JSON.stringify(value, null, 2))}</pre>`;
    tools.appendChild(section);
  }
}

function label(value) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function escapeHtml(value) {
  return value.replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[char]));
}
