const statusCards = document.querySelector("#status-cards");
const incidentsEl = document.querySelector("#incidents");
const probesEl = document.querySelector("#probes");
const devicesEl = document.querySelector("#devices");
const timelineEl = document.querySelector("#timeline");
const overallPill = document.querySelector("#overall-pill");
const overallTs = document.querySelector("#overall-ts");
const incidentHours = document.querySelector("#incident-hours");
const timelineHours = document.querySelector("#timeline-hours");

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Request failed for ${url}`);
  }
  return response.json();
}

function formatTs(ts) {
  return new Date(ts).toLocaleString();
}

function classificationTone(classification) {
  if (classification === "healthy") return "pill-ok";
  if (classification === "dns_only" || classification === "http_only") return "pill-warn";
  return "pill-bad";
}

function renderStatus(payload) {
  const status = payload.status;
  const probes = payload.probes;
  if (!status) {
    overallPill.textContent = "No Data";
    overallPill.className = "pill pill-neutral";
    overallTs.textContent = "";
    return;
  }

  overallPill.textContent = status.classification.replaceAll("_", " ");
  overallPill.className = `pill ${classificationTone(status.classification)}`;
  overallTs.textContent = `Updated ${formatTs(status.ts)}`;

  const groups = [
    ["Gateway", probes.find((item) => item.target_kind === "gateway")],
    ["Upstream", probes.find((item) => item.target_kind === "upstream")],
    ["Internet ICMP", probes.find((item) => item.target_name === "icmp-1.1.1.1")],
    ["DNS", probes.find((item) => item.probe_type === "dns")],
    ["HTTP", probes.find((item) => item.probe_type === "http")]
  ];

  statusCards.innerHTML = groups.map(([label, probe]) => {
    const ok = probe?.success;
    const latency = probe?.latency_ms == null ? "n/a" : `${probe.latency_ms.toFixed(1)} ms`;
    return `
      <div class="status-tile">
        <div class="status-label">${label}</div>
        <div class="status-main">${ok ? "OK" : "FAIL"}</div>
        <div class="status-sub">${latency}</div>
        <div class="status-sub mono">${probe ? probe.target_address : ""}</div>
      </div>
    `;
  }).join("");

  probesEl.innerHTML = tableHtml(
    ["Time", "Kind", "Target", "Probe", "Success", "Latency"],
    probes.map((item) => [
      formatTs(item.ts),
      item.target_kind,
      `${item.target_name} (${item.target_address})`,
      item.probe_type,
      item.success ? "yes" : "no",
      item.latency_ms == null ? "n/a" : `${item.latency_ms.toFixed(1)} ms`
    ])
  );
}

function renderIncidents(payload) {
  const incidents = payload.incidents;
  if (!incidents.length) {
    incidentsEl.innerHTML = `<div class="incident healthy-empty"><div class="incident-top"><span>No incidents</span><span>All healthy</span></div><div class="incident-meta">No non-healthy cycles in this window.</div></div>`;
    return;
  }

  incidentsEl.innerHTML = incidents.map((item) => `
    <div class="incident">
      <div class="incident-top">
        <span>${item.classification.replaceAll("_", " ")}</span>
        <span>${item.cycles} cycles</span>
      </div>
      <div class="incident-meta">
        ${formatTs(item.start_ts)} to ${formatTs(item.end_ts)}
      </div>
      <div class="incident-meta">
        gateway=${item.gateway_ok ? "up" : "down"} upstream=${item.upstream_ok ? "up" : "down"} internet=${item.internet_icmp_ok ? "up" : "down"} dns=${item.dns_ok ? "up" : "down"} http=${item.http_ok ? "up" : "down"}
      </div>
    </div>
  `).join("");
}

function renderTimeline(payload) {
  const labels = [
    ["gateway", "Gateway"],
    ["upstream", "Upstream"],
    ["internet_icmp", "Internet ICMP"],
    ["dns", "DNS"],
    ["http", "HTTP"]
  ];
  timelineEl.innerHTML = labels.map(([key, label]) => {
    const cells = payload.series[key].map((item) => `<div class="timeline-cell ${item.ok ? "ok" : "bad"}" title="${label} ${formatTs(item.ts)} ${item.ok ? "OK" : "FAIL"}"></div>`).join("");
    return `
      <div class="timeline-row">
        <div class="timeline-label">${label}</div>
        <div class="timeline-bar">${cells}</div>
      </div>
    `;
  }).join("");
}

function renderDevices(payload) {
  devicesEl.innerHTML = tableHtml(
    ["Address", "Name", "MAC", "Kind", "Last Seen"],
    payload.devices.map((item) => [
      item.address,
      item.name,
      item.mac_address || "",
      item.kind,
      formatTs(item.last_seen)
    ])
  );
}

function tableHtml(headers, rows) {
  const head = headers.map((item) => `<th>${item}</th>`).join("");
  const body = rows.map((row) => `<tr>${row.map((col) => `<td>${col}</td>`).join("")}</tr>`).join("");
  return `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}

async function loadStatus() {
  renderStatus(await fetchJson("/api/status"));
}

async function loadIncidents() {
  renderIncidents(await fetchJson(`/api/incidents?hours=${incidentHours.value}`));
}

async function loadTimeline() {
  renderTimeline(await fetchJson(`/api/timeline?hours=${timelineHours.value}`));
}

async function loadDevices() {
  renderDevices(await fetchJson("/api/discovered?limit=100"));
}

async function refreshAll() {
  try {
    await Promise.all([loadStatus(), loadIncidents(), loadTimeline(), loadDevices()]);
  } catch (error) {
    console.error(error);
  }
}

incidentHours.addEventListener("change", loadIncidents);
timelineHours.addEventListener("change", loadTimeline);

refreshAll();
setInterval(refreshAll, 15000);
