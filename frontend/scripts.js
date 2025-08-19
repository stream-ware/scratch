// Determine backend API base. When served via file:// or any dev port, use localhost:8000
const API = (() => {
  try {
    const { protocol, hostname } = location;
    if (!hostname) return "http://localhost:8000";
    const safeProto = protocol.startsWith("http") ? protocol : "http:";
    return `${safeProto}//${hostname}:8000`;
  } catch (_) {
    return "http://localhost:8000";
  }
})();

async function getJSON(url) {
  const res = await fetch(url);
  return res.json();
}

function setPre(id, data) {
  document.getElementById(id).textContent = JSON.stringify(data, null, 2);
}

async function refreshHealth() {
  const data = await getJSON(`${API}/api/health`);
  setPre("health", data);
}

async function refreshStreams() {
  const list = document.getElementById("streams");
  list.innerHTML = "";
  const streams = await getJSON(`${API}/api/streams`);
  streams.forEach((s) => {
    const li = document.createElement("li");
    li.textContent = `${s.name} (${s.protocol}) -> ${s.url}`;
    list.appendChild(li);
  });
}

async function doPing() {
  const host = document.getElementById("ping-host").value || "8.8.8.8";
  const data = await getJSON(`${API}/api/monitor/ping?host=${encodeURIComponent(host)}`);
  setPre("ping", data);
}

async function doExport() {
  const res = await fetch(`${API}/api/export`, { method: "POST" });
  const data = await res.json();
  setPre("export", data);
}

addEventListener("DOMContentLoaded", () => {
  document.getElementById("btn-health").addEventListener("click", refreshHealth);
  document.getElementById("btn-streams").addEventListener("click", refreshStreams);
  document.getElementById("btn-ping").addEventListener("click", doPing);
  document.getElementById("btn-export").addEventListener("click", doExport);

  // initial
  refreshHealth();
  refreshStreams();
});
