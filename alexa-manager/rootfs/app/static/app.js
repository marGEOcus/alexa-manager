/* Alexa Manager - SPA (deutsch, HA-Style) */
(() => {
"use strict";

// ---------------------------------------------------------------------------
// Helfer
// ---------------------------------------------------------------------------
const $ = (sel, el = document) => el.querySelector(sel);

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

async function api(path, method = "GET", body) {
  const opts = { method };
  opts.headers = { "X-Panel-Url": location.href };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const resp = await fetch(path, opts);
  let data = null;
  try { data = await resp.json(); } catch { data = null; }
  if (!resp.ok) {
    const detail = data?.detail || data?.error || `HTTP ${resp.status}`;
    const err = new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    err.status = resp.status;
    throw err;
  }
  return data;
}

function toast(msg, kind = "ok") {
  const root = $("#toastRoot");
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.innerHTML = `<span class="t-icon">${ic(kind === "err" ? "warning" : "check", 18)}</span><span>${esc(msg)}</span>`;
  root.appendChild(el);
  setTimeout(() => el.remove(), kind === "err" ? 6500 : 4000);
}

function parseMaybe(s) {
  if (s === null || s === undefined) return null;
  if (typeof s === "object") return s;
  try { return JSON.parse(s); } catch { return null; }
}

const DAY_DE = { MO: "Mo", TU: "Di", WE: "Mi", TH: "Do", FR: "Fr", SA: "Sa", SU: "So" };

// ---------------------------------------------------------------------------
// Icons (Material-artig, 24er-Raster)
// ---------------------------------------------------------------------------
const ICONS = {
  alexa: "<circle cx='12' cy='12' r='11' fill='currentColor' opacity='.15'/><path d='M5 14.5c1.8 2.6 4.2 3.9 7 3.9s5.2-1.3 7-3.9' stroke='currentColor' stroke-width='1.8' fill='none' stroke-linecap='round'/><circle cx='8.5' cy='9' r='1.3' fill='currentColor'/><circle cx='15.5' cy='9' r='1.3' fill='currentColor'/>",
  home: "M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z",
  devices: "M17 1H7c-1.1 0-2 .9-2 2v18c0 1.1.9 2 2 2h10c1.1 0 2-.9 2-2V3c0-1.1-.9-2-2-2zm0 18H7V3h10v16z",
  scenes: "M9 21c0 .55.45 1 1 1h4c.55 0 1-.45 1-1v-1H9v1zm3-19C8.14 2 5 5.14 5 9c0 2.38 1.19 4.47 3 5.74V17c0 .55.45 1 1 1h6c.55 0 1-.45 1-1v-2.26c1.81-1.27 3-3.36 3-5.74 0-3.86-3.14-7-7-7zm2 14h-4v-1.28c0-.38.21-.72.54-.88.98-.49 1.56-1.54 1.56-2.84 0-1.1.9-2 2-2s2 .9 2 2c0 1.3.58 2.35 1.56 2.84.33.16.54.5.54.88V16z",
  groups: "M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.17.86 1.97 2.05 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z",
  routines: "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z",
  settings: "M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.03-.64-.07-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.04.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z",
  close: "M19 6.41 17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z",
  search: "M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z",
  plus: "M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z",
  trash: "M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z",
  power: "M13 3h-2v10h2V3zm4.83 2.41-1.41 1.41C17.93 7.86 19 9.81 19 12c0 3.87-3.13 7-7 7s-7-3.13-7-7c0-2.19 1.07-4.14 2.58-5.41L6.17 5.41C4.23 6.99 3 9.39 3 12c0 4.97 4.02 9 9 9s9-4.03 9-9c0-2.61-1.23-5.01-3.17-6.59z",
  check: "M9 16.17 4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z",
  refresh: "M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.98 0 7.21-2.86 7.92-6.66h-2.06c-.68 2.49-2.94 4.37-5.86 4.37-3.31 0-6.02-2.71-6.02-6.02s2.71-6.02 6.02-6.02c1.55 0 2.94.64 3.98 1.68L14 10h7V3l-3.35 3.35z",
  warning: "M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z",
  edit: "M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z",
  play: "M8 5v14l11-7z",
  plug: "M16 7V3h-4v4H8V3H4v4h4v4l-2 2 4 4 4-4-2-2h4V7z",
  light: "M9 21c0 .55.45 1 1 1h4c.55 0 1-.45 1-1v-1H9v1zm3-19C8.14 2 5 5.14 5 9c0 2.38 1.19 4.47 3 5.74V17c0 .55.45 1 1 1h6c.55 0 1-.45 1-1v-2.26c1.81-1.27 3-3.36 3-5.74 0-3.86-3.14-7-7-7z",
  sensor: "M12 2 4 5v6c0 5.55 3.84 10.74 8 12 4.16-1.26 8-6.45 8-12V5l-8-3z",
  speaker: "M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z",
  lock: "M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2z",
  camera: "M12 9c-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4-1.79-4-4-4zm0 6c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zM4 5h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z",
  thermo: "M15 13V5c0-1.66-1.34-3-3-3S9 3.34 9 5v8c-1.24.61-2 1.91-2 3.4 0 2.21 1.79 4 4 4s4-1.79 4-4c0-1.49-.76-2.79-2-3.4zm-2-7.2c.66 0 1.2.54 1.2 1.2v.1c0 .66-.54 1.2-1.2 1.2s-1.2-.54-1.2-1.2v-.1c0-.66.54-1.2 1.2-1.2z",
  fan: "M12 8c-2.21 0-4-1.79-4-4s1.79-4 4-4 4 1.79 4 4-1.79 4-4 4zm0 2c2.21 0 4 1.79 4 4s-1.79 4-4 4-4-1.79-4-4 1.79-4 4-4zm7.2 1.2c0-2.21-1.79-4-4-4s-4 1.79-4 4 1.79 4 4 4 4-1.79 4-4zm-14.4 0c0-2.21-1.79-4-4-4v0c-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4z",
};

function ic(name, size = 20) {
  const raw = ICONS[name] || ICONS.plug;
  // Rohe Pfad-Daten (z. B. "M10 20v-6…") müssen in <path> gewickelt werden,
  // sonst rendert der Browser nichts (Textknoten im <svg>).
  const body = raw.includes("<") ? raw : `<path d="${raw}"></path>`;
  return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">${body}</svg>`;
}

function categoryIcon(cat) {
  const c = String(cat || "").toUpperCase();
  if (c.includes("LIGHT")) return "light";
  if (c.includes("SPEAKER")) return "speaker";
  if (c.includes("SENSOR")) return "sensor";
  if (c.includes("LOCK")) return "lock";
  if (c.includes("CAMERA")) return "camera";
  if (c.includes("THERM")) return "thermo";
  if (c.includes("FAN")) return "fan";
  if (c.includes("SWITCH") || c.includes("PLUG") || c.includes("OUTLET")) return "plug";
  return "devices";
}

// ---------------------------------------------------------------------------
// Zustand
// ---------------------------------------------------------------------------
const S = {
  tab: "devices",
  status: null,
  account: null,
  devices: [],
  groups: [],
  routines: [],
  devChip: "all",          // Stat-Chip-Filter: all|online|offline|unknown|echo|groups|ha
  devStatus: "all",        // Status-Combo: all|online|offline|unknown|enabled|disabled
  devType: "",             // Typ-Combo: "" = alle
  deviceGroup: "",         // Gruppen-Combo
  search: "",
  devSel: new Set(),       // ausgewählte Geräte (endpointId/applianceId)
};

const TABS = [
  ["overview", "Übersicht", "home"],
  ["devices", "Geräte", "devices"],
  ["routines", "Routinen", "routines"],
  ["settings", "Einstellungen", "settings"],
];

// ---------------------------------------------------------------------------
// Topbar / Tabs / Session-Chip
// ---------------------------------------------------------------------------
function renderTabs() {
  $("#tabs").innerHTML = TABS.map(([id, label, icon]) =>
    `<button class="tab-btn ${S.tab === id ? "active" : ""}" data-tab="${id}">
      ${ic(icon, 17)}<span>${label}</span></button>`).join("");
  $("#tabs").querySelectorAll("[data-tab]").forEach((b) =>
    b.onclick = () => go(b.dataset.tab));
  $("#brandIcon").innerHTML = ic("alexa", 26);
}

function updateSessionChip() {
  const chip = $("#sessionChip");
  const st = S.status;
  if (!st) return;
  if (st.state === "ready") {
    chip.className = "chip ok";
    chip.innerHTML = `<span class="dot"></span>${esc(st.email || "Verbunden")}`;
    chip.classList.remove("hidden");
  } else {
    chip.className = "chip err";
    chip.innerHTML = `<span class="dot"></span>Kein Amazon-Konto`;
    chip.classList.remove("hidden");
  }
}

async function refreshStatus() {
  try {
    S.status = await api("api/status");
    updateSessionChip();
    return S.status;
  } catch {
    S.status = { state: "none", detail: "Add-on nicht erreichbar" };
    updateSessionChip();
    return S.status;
  }
}

function go(tab) {
  S.tab = tab;
  renderTabs();
  closeDrawer();
  render();
}

// ---------------------------------------------------------------------------
// Drawer
// ---------------------------------------------------------------------------
function openDrawer(title, bodyHTML) {
  $("#drawerTitle").textContent = title || "";
  $("#drawerBody").innerHTML = bodyHTML;
  $("#drawer").classList.remove("hidden");
}
function closeDrawer() { $("#drawer").classList.add("hidden"); }
$("#drawerClose").innerHTML = ic("close", 20);
$("#drawerClose").onclick = closeDrawer;
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") { closeDrawer(); closeDialog(); }
});

// ---------------------------------------------------------------------------
// Dialoge
// ---------------------------------------------------------------------------
function openDialog(title, bodyHTML, footHTML) {
  closeDialog();
  const root = $("#dialogRoot");
  root.innerHTML = `<div class="dialog-overlay"><div class="dialog">
    <div class="head">${esc(title)}</div>
    <div class="body">${bodyHTML}</div>
    <div class="foot">${footHTML || ""}</div>
  </div></div>`;
  root.classList.remove("hidden");
  root._overlay = $(".dialog-overlay", root);
  root._overlay.onclick = (e) => { if (e.target === root._overlay) closeDialog(); };
  return root;
}
function closeDialog() {
  const root = $("#dialogRoot");
  root.classList.add("hidden");
  root.innerHTML = "";
  root._overlay = null;
}

function confirmDialog(title, text, okLabel = "OK", danger = false) {
  return new Promise((resolve) => {
    const root = openDialog(
      title,
      `<p style="margin:8px 0 4px;font-size:14px;">${text}</p>`,
      `<button class="btn secondary" data-act="no">Abbrechen</button>
       <button class="btn ${danger ? "danger" : ""}" data-act="yes">${esc(okLabel)}</button>`
    );
    root.querySelector('[data-act=no]').onclick = () => { closeDialog(); resolve(false); };
    root.querySelector('[data-act=yes]').onclick = () => { closeDialog(); resolve(true); };
  });
}

async function deleteConfirm(title, name) {
  return new Promise((resolve) => {
    const root = openDialog(
      title,
      `<p style="margin:8px 0 12px;font-size:14px;">Dies löscht <b>${esc(name)}</b> dauerhaft bei Amazon.
       Eingetragen wird der Befehl erst nach Bestätigung.</p>
       <label class="field"><span class="lbl">Bitte zur Sicherheit eingeben:</span>
       <input type="text" id="delWord" autocomplete="off" placeholder="DELETE"></label>`,
      `<button class="btn secondary" data-act="no">Abbrechen</button>
       <button class="btn danger" data-act="yes" disabled>Löschen</button>`
    );
    const inp = $("#delWord", root);
    const yes = root.querySelector('[data-act=yes]');
    inp.oninput = () => { yes.disabled = inp.value.trim().toUpperCase() !== "DELETE"; };
    inp.focus();
    root.querySelector('[data-act=no]').onclick = () => { closeDialog(); resolve(false); };
    yes.onclick = () => { closeDialog(); resolve(true); };
  });
}

// ---------------------------------------------------------------------------
// Render-Root
// ---------------------------------------------------------------------------
async function render() {
  const c = $("#content");
  // Geräte-Seite: nur die Tabelle scrollt -> kein unterer Main-Abstand
  c.classList.toggle("no-pad", S.tab === "devices");
  syncDevCheckAll();
  c.innerHTML = `<div class="empty"><div class="big">…</div>Wird geladen …</div>`;
  if (S.status && S.status.state !== "ready" && S.tab !== "settings") {
    c.innerHTML = `
      <div class="notice">Amazon-Konto nicht verbunden. Verbinde dein Amazon-Konto in den Einstellungen (E-Mail, Passwort, ggf. 2-Faktor-Code). Es wird nur der Refresh-Token gespeichert – kein Passwort.</div>
      <div style="margin-top:10px"><button class="btn" id="goSettings">Zu den Einstellungen</button></div>`;
    $("#goSettings").onclick = () => go("settings");
    return;
  }
  try {
    switch (S.tab) {
      case "overview": await renderOverview(c); break;
      case "devices": await renderDevices(c); break;
      case "routines": await renderRoutines(c); break;
      case "settings": await renderSettings(c); break;
    }
  } catch (ex) {
    if (ex.status === 401) { go("settings"); return; }
    c.innerHTML = `<div class="notice err">${esc(ex.message)}</div>
      <div style="margin-top:10px"><button class="btn secondary" onclick="location.reload()">Erneut versuchen</button></div>`;
  }
}

// ---------------------------------------------------------------------------
// Übersicht
// ---------------------------------------------------------------------------
async function renderOverview(c) {
  const [devices, routines, account] = await Promise.all([
    api("api/devices"), api("api/routines"), api("api/account"),
  ]);
  S.devices = devices; S.routines = routines; S.account = account;
  const online = devices.filter((d) => reachLabel(d)[0] === "Erreichbar").length;
  const enabledRoutines = routines.filter((r) => r.status === "ENABLED").length;
  c.innerHTML = `
    <div class="page-head"><div class="spacer"></div>
      <div class="actions"><button class="btn secondary small" id="ovRefresh">${ic("refresh", 16)}<span>Neu laden</span></button></div>
    </div>
    <div class="grid cols-4">
      <div class="stat"><div class="num">${devices.length}</div><div class="lbl">Geräte (${online} erreichbar)</div></div>
      <div class="stat"><div class="num">${routines.length}</div><div class="lbl">Routinen (${enabledRoutines} aktiv)</div></div>
    </div>
    <div class="card" style="margin-top:14px">
      <h2>Amazon-Konto</h2>
      <div class="kv">
        <span class="k">Konto</span><span class="v">${esc(S.status?.email || "")}</span>
        <span class="k">Domain</span><span class="v">${esc(S.status?.domain || "amazon.de")}</span>
        <span class="k">Customer-ID</span><span class="v">${esc(account.customerId || "–")}</span>
        <span class="k">Echo-Geräte</span><span class="v">${account.echoes.map((e) => esc(e.name)).join(", ") || "–"}</span>
      </div>
      <div class="hint" style="margin-top:10px">Sitzung wird automatisch aus dem gespeicherten Refresh-Token erneuert – ein erneutes Anmelden ist in der Regel nicht nötig.</div>
    </div>`;
  $("#ovRefresh").onclick = render;
}

// ---------------------------------------------------------------------------
// Geräte
// ---------------------------------------------------------------------------
function reachLabel(d) {
  // reachable = reachabilityStatusValue (z. B. "OK"/"UNREACHABLE") oder
  // availability (z. B. "ONLINE"/"OFFLINE") - "OK" heißt online!
  const v = String(d.reachable || d.availability || "").toLowerCase();
  if (!v || v === "none") return ["Unbekannt", ""];
  if (v.includes("unreachable") || v === "offline") return ["Unreichbar", "warn"];
  if (v === "ok" || v.includes("reachable") || v === "online") return ["Erreichbar", "ok"];
  return ["Unbekannt", ""];
}

let devSort = { key: "name", dir: 1 };

function devId(d) { return d.endpointId || d.applianceId || ""; }
function isEcho(d) {
  // Echo = Rohdateneintrag "value": "ALEXA_VOICE_ENABLED"
  // (endpoint.displayCategories.primary.value = category).
  const ep = (d.details || {}).endpoint || {};
  return [d.category, (((ep.displayCategories || {}).primary) || {}).value]
    .some((v) => String(v || "").toUpperCase() === "ALEXA_VOICE_ENABLED");
}
function isHA(d) {
  return String(d.manufacturer || "").toLowerCase().includes("home assistant");
}
function devTypeOf(d) { return d.category || d.skill || "OTHER"; }

// Kompakt-Tabellen-Logik (Aura-Device-Master-Style): Zeilen HTML + Events
// getrennt, damit der Such-Input beim Tippen NICHT neu gerendert wird
// (sonst fallen Zeichen durch den Re-Render).
function filteredDevices() {
  let list = S.devices;
  const q = S.search.toLowerCase();
  if (q) list = list.filter((d) =>
    [d.name, devDesc(d), d.skill, d.category, d.manufacturer, d.endpointId]
      .join(" ").toLowerCase().includes(q));
  const chip = S.devChip || "all";
  if (chip === "online") list = list.filter((d) => reachLabel(d)[0] === "Erreichbar");
  else if (chip === "offline") list = list.filter((d) => reachLabel(d)[0] === "Unreichbar");
  else if (chip === "unknown") list = list.filter((d) => reachLabel(d)[0] === "Unbekannt");
  else if (chip === "echo") list = list.filter(isEcho);
  else if (chip === "groups") list = list.filter((d) => (d.groups || []).length > 0);
  else if (chip === "ha") list = list.filter(isHA);
  const st = S.devStatus || "all";
  if (st === "online") list = list.filter((d) => reachLabel(d)[0] === "Erreichbar");
  else if (st === "offline") list = list.filter((d) => reachLabel(d)[0] === "Unreichbar");
  else if (st === "unknown") list = list.filter((d) => reachLabel(d)[0] === "Unbekannt");
  else if (st === "enabled") list = list.filter((d) => d.enabled);
  else if (st === "disabled") list = list.filter((d) => !d.enabled);
  if (S.devType) list = list.filter((d) => devTypeOf(d) === S.devType);
  if (S.deviceGroup) list = list.filter((d) => (d.groups || []).includes(S.deviceGroup));
  const val = (d) => {
    switch (devSort.key) {
      case "desc": return devDesc(d).toLowerCase();
      case "type": return devTypeOf(d).toLowerCase();
      case "status": {
        const l = reachLabel(d)[0];
        return l === "Erreichbar" ? 0 : l === "Unbekannt" ? 1 : 2;
      }
      case "id": return (d.endpointId || "").toLowerCase();
      default: return (d.name || "").toLowerCase();
    }
  };
  list = [...list].sort((a, b) => {
    const av = val(a), bv = val(b);
    return (av === bv ? 0 : av > bv ? 1 : -1) * devSort.dir;
  });
  return list;
}

function devDesc(d) {
  const cv = (d.details || {}).legacyAppliance || {};
  return cv.friendlyDescription ||
    [d.manufacturer, d.model || cv.modelName].filter(Boolean).join(" ") || "";
}

function devStats(list) {
  let on = 0, off = 0, unk = 0, echo = 0, ha = 0, inGrp = 0;
  for (const d of list) {
    const l = reachLabel(d)[0];
    if (l === "Erreichbar") on++;
    else if (l === "Unreichbar") off++;
    else unk++;
    if (isEcho(d)) echo++;
    if (isHA(d)) ha++;
    if ((d.groups || []).length > 0) inGrp++;
  }
  return [
    ["devices", "Gesamt", list.length, "", "all"],
    ["power", "Online", on, "ok", "online"],
    ["power", "Offline", off, "err", "offline"],
    ["devices", "Unbekannt", unk, "", "unknown"],
    ["speaker", "Echos", echo, "", "echo"],
    ["groups", "Gruppen", inGrp, "", "groups"],
    ["home", "Home Assistant", ha, "", "ha"],
  ];
}

function deviceRowsHtml(list) {
  if (!list.length) {
    return `<tr><td colspan="8"><div class="empty"><div class="big">${ic("devices", 40)}</div>Keine Geräte gefunden.</div></td></tr>`;
  }
  return list.map((d) => {
    const [rl] = reachLabel(d);
    const st = rl === "Erreichbar" ? ["Online", "ok"]
      : rl === "Unreichbar" ? ["Offline", "err"] : ["Unbekannt", ""];
    const id = devId(d);
    return `<tr class="clickable ${S.devSel.has(id) ? "sel" : ""}" data-id="${esc(id)}">
      <td class="c-check"><input type="checkbox" class="row-check" ${S.devSel.has(id) ? "checked" : ""} aria-label="Gerät auswählen"></td>
      <td class="c-name">${esc(d.name || "Ohne Name")}</td>
      <td class="c-desc"><span title="${esc(devDesc(d))}">${esc(devDesc(d)) || "–"}</span></td>
      <td><span class="badge">${esc(d.category || d.skill || "OTHER")}</span></td>
      <td><div class="st-main ${st[1]}">${st[0]}</div>
        <div class="st-sub">Alexa: ${d.enabled ? "Aktiviert" : "Deaktiviert"}</div></td>
      <td class="muted">Alexa</td>
      <td><span class="id-mono" title="${esc(d.endpointId || "")}">${esc(d.endpointId || "–")}</span></td>
      <td class="right"><div class="row-actions">
        <button class="row-btn" data-act="toggle" title="${d.enabled ? "Deaktivieren" : "Aktivieren"}">${ic("power", 15)}</button>
        <button class="row-btn danger" data-act="del" title="Löschen">${ic("trash", 15)}</button>
      </div></td>
    </tr>`;
  }).join("");
}

function bindDeviceRows(c) {
  c.querySelectorAll("tr[data-id]").forEach((tr) => {
    const d = () => S.devices.find((x) => devId(x) === tr.dataset.id);
    tr.onclick = () => { const x = d(); if (x) openDevice(x); };
    const chk = tr.querySelector(".row-check");
    if (chk) chk.onclick = (e) => {
      e.stopPropagation();
      const id = tr.dataset.id;
      if (chk.checked) S.devSel.add(id); else S.devSel.delete(id);
      tr.classList.toggle("sel", chk.checked);
      syncDevSelUI(c);
    };
    const tog = tr.querySelector('[data-act="toggle"]');
    if (tog) tog.onclick = async (e) => {
      e.stopPropagation();
      const x = d(); if (!x) return;
      const ok = await confirmDialog(
        "Gerät " + (x.enabled ? "deaktivieren" : "aktivieren") + "?",
        x.name || "Ohne Name");
      if (!ok) return;
      try {
        await api("api/devices/enable", "POST", { endpointId: x.endpointId, enabled: !x.enabled });
        x.enabled = !x.enabled;
        applyDeviceFilter(c);
        toast(`"${x.name}" ${x.enabled ? "aktiviert" : "deaktiviert"}.`);
      } catch (ex) { toast(ex.message, "err"); }
    };
    const del = tr.querySelector('[data-act="del"]');
    if (del) del.onclick = async (e) => {
      e.stopPropagation();
      const x = d(); if (!x) return;
      const ok = await deleteConfirm("Gerät löschen", x.name || "das Gerät");
      if (!ok) return;
      try {
        await api("api/devices/delete", "POST", { endpointId: x.endpointId, applianceId: x.applianceId });
        S.devices = S.devices.filter((y) => y !== x);
        applyDeviceFilter(c);
        toast("Gerät gelöscht (sofern nicht vom Skill neu erkannt wird).");
      } catch (ex) { toast(ex.message, "err"); }
    };
  });
}

function applyDeviceFilter(c) {
  const tb = c.querySelector("table.list tbody");
  if (!tb) return;
  tb.innerHTML = deviceRowsHtml(filteredDevices());
  bindDeviceRows(c);
  syncDevCheckAll();
}

function selectedDevices() {
  return S.devices.filter((d) => S.devSel.has(devId(d)));
}

function syncDevSelUI(c) {
  const bb = c && c.querySelector(".dev-bottombar");
  if (bb) {
    const cnt = bb.querySelector(".sel-count");
    if (cnt) cnt.textContent = S.devSel.size ? `${S.devSel.size} ausgewählt` : "Keine Auswahl";
    // Nur die Auswahl-Buttons deaktivieren (nicht z. B. "Neu laden")
    bb.querySelectorAll("button.sel-act").forEach((b) => { b.disabled = S.devSel.size === 0; });
  }
  syncDevCheckAll();
}

// "Alle"-Checkbox im Tabellen-Header (nur auf der Gerate-Seite vorhanden)
function syncDevCheckAll() {
  const chk = $("#devCheckAll");
  if (!chk) return;
  const ids = filteredDevices().map(devId);
  const sel = ids.filter((id) => S.devSel.has(id));
  chk.checked = ids.length > 0 && sel.length === ids.length;
  chk.indeterminate = sel.length > 0 && sel.length < ids.length;
}

async function renderDevices(c) {
  if (!S.devices.length || !S.account) S.devices = await api("api/devices");
  if (!S.groups.length) { try { S.groups = await api("api/groups"); } catch { S.groups = []; } }
  const chip = S.devChip || "all";
  const sortAr = (k) => devSort.key === k ? (devSort.dir === 1 ? " ↑" : " ↓") : "";
  const types = [...new Set(S.devices.map(devTypeOf))]
    .sort((a, b) => a.localeCompare(b, "de"));
  c.innerHTML = `
    <div class="dev-page">
      <div class="stat-cards">
        ${devStats(S.devices).map(([i, l, n, k, cid]) =>
          `<div class="stat-card clickable ${chip === cid ? "active" : ""}" data-chip="${cid}"><span class="s-ic ${k}">${ic(i, 18)}</span>
           <span class="s-num">${n}</span><span class="s-lbl">${l}</span></div>`).join("")}
      </div>
      <div class="dev-filter-row">
        <div class="search">${ic("search", 18)}<input id="devSearch" placeholder="Gerät suchen (Name, Beschreibung, Typ, ID …)" value="${esc(S.search)}"><button class="search-clear" id="devClear" title="Filter löschen" ${S.search ? "" : "hidden"}>${ic("close", 14)}</button></div>
        <select id="devGroup" class="combo" title="Nach Gruppe filtern">
          <option value="">Alle Gruppen</option>
          ${(S.groups || []).slice().sort((a, b) => String(a.name || "").localeCompare(String(b.name || ""), "de"))
            .map((g) => { const n = g.name || g.groupId || "?";
              return `<option value="${esc(n)}" ${S.deviceGroup === n ? "selected" : ""}>${esc(n)}</option>`; }).join("")}
        </select>
        <select id="devType" class="combo" title="Nach Typ filtern">
          <option value="">Alle Gerätetypen</option>
          ${types.map((t) => `<option value="${esc(t)}" ${S.devType === t ? "selected" : ""}>${esc(t)}</option>`).join("")}
        </select>
        <select id="devStatus" class="combo" title="Nach Status filtern">
          ${[["all", "Alle Status"], ["online", "Online"], ["offline", "Offline"],
             ["unknown", "Unbekannt"], ["enabled", "Aktiviert"], ["disabled", "Deaktiviert"]]
            .map(([v, l]) => `<option value="${v}" ${(S.devStatus || "all") === v ? "selected" : ""}>${l}</option>`).join("")}
        </select>
      </div>
      <div class="card table-card dev-table-card">
        <table class="list compact"><thead>
        <tr>
          <th class="c-check"><input type="checkbox" class="row-check" id="devCheckAll" title="Alle gefilterten Geräte auswählen/abwählen"></th>
          <th class="sortable" data-sort="name" title="Nach Name sortieren">Name<span class="sort-ar">${sortAr("name")}</span></th>
          <th class="sortable" data-sort="desc" title="Nach Beschreibung sortieren">Beschreibung<span class="sort-ar">${sortAr("desc")}</span></th>
          <th class="sortable" data-sort="type" title="Nach Typ sortieren">Typ<span class="sort-ar">${sortAr("type")}</span></th>
          <th class="sortable" data-sort="status" title="Nach Status sortieren">Status<span class="sort-ar">${sortAr("status")}</span></th>
          <th>Quelle</th>
          <th class="sortable" data-sort="id" title="Nach ID sortieren">ID<span class="sort-ar">${sortAr("id")}</span></th>
          <th class="right">Aktionen</th>
        </tr>
        </thead><tbody>
        ${deviceRowsHtml(filteredDevices())}
        </tbody></table>
      </div>
      <div class="dev-bottombar">
        <span class="sel-count">Keine Auswahl</span>
        <button class="btn danger-solid sel-act" id="devDelete">${ic("trash", 16)}<span>Löschen</span></button>
        <button class="btn solid sel-act" id="devDisable">${ic("power", 16)}<span>Deaktivieren</span></button>
        <button class="btn solid sel-act" id="devEnable">${ic("power", 16)}<span>Aktivieren</span></button>
        <span class="spacer"></span>
        <button class="btn secondary small" id="devRefresh">${ic("refresh", 16)}<span>Neu laden</span></button>
      </div>
    </div>`;
  $("#devRefresh").onclick = async () => { S.devices = await api("api/devices"); render(); };
  $("#devSearch").oninput = (e) => {
    S.search = e.target.value;
    $("#devClear").hidden = !S.search;
    applyDeviceFilter(c);
  };
  $("#devClear").onclick = () => {
    S.search = "";
    $("#devSearch").value = "";
    $("#devClear").hidden = true;
    applyDeviceFilter(c);
  };
  c.querySelectorAll(".stat-card[data-chip]").forEach((el) => el.onclick = () => {
    const cid = el.dataset.chip;
    S.devChip = (cid === "all" || S.devChip === cid) ? "all" : cid;
    c.querySelectorAll(".stat-card[data-chip]").forEach((x) =>
      x.classList.toggle("active",
        x.dataset.chip === (S.devChip === "all" ? "all" : S.devChip)));
    applyDeviceFilter(c);
  });
  $("#devGroup").onchange = (e) => { S.deviceGroup = e.target.value; applyDeviceFilter(c); };
  $("#devType").onchange = (e) => { S.devType = e.target.value; applyDeviceFilter(c); };
  $("#devStatus").onchange = (e) => { S.devStatus = e.target.value; applyDeviceFilter(c); };
  c.querySelectorAll("thead th[data-sort]").forEach((th) => th.onclick = () => {
    const k = th.dataset.sort;
    if (devSort.key === k) devSort.dir *= -1;
    else { devSort.key = k; devSort.dir = 1; }
    c.querySelectorAll("thead th[data-sort]").forEach((x) => {
      x.querySelector(".sort-ar").textContent =
        x.dataset.sort === devSort.key ? (devSort.dir === 1 ? " ↑" : " ↓") : "";
    });
    applyDeviceFilter(c);
  });
  $("#devCheckAll").onchange = () => {
    const ids = filteredDevices().map(devId);
    const all = $("#devCheckAll").checked;
    ids.forEach((id) => { if (all) S.devSel.add(id); else S.devSel.delete(id); });
    applyDeviceFilter(c);
    syncDevSelUI(c);
  };
  $("#devDelete").onclick = () => { const devs = selectedDevices(); if (devs.length) bulkDelete(devs); };
  $("#devEnable").onclick = () => { const devs = selectedDevices(); if (devs.length) bulkEnable(devs, true); };
  $("#devDisable").onclick = () => { const devs = selectedDevices(); if (devs.length) bulkEnable(devs, false); };
  bindDeviceRows(c);
  syncDevSelUI(c);
}

async function bulkEnable(devs, enabled) {
  const todo = devs.filter((d) => d.endpointId);
  if (!todo.length) return toast("Kein Gerät mit Endpoint-ID – Aktivieren/Deaktivieren geht nur über die Alexa-API.", "err");
  let ok = 0;
  for (const d of todo) {
    try {
      await api("api/devices/enable", "POST", { endpointId: d.endpointId, enabled });
      ok++;
    } catch (ex) { toast(`${d.name || "Gerät"}: ${ex.message}`, "err"); }
  }
  S.devices = await api("api/devices");
  render();
  toast(`${ok} von ${todo.length} Gerät(en) ${enabled ? "aktiviert" : "deaktiviert"}.`);
}

async function bulkDelete(devs) {
  const ok = await deleteConfirm(
    "Geräte löschen",
    devs.length === 1 ? "dieses 1 Gerät" : `diese ${devs.length} Geräte`);
  if (!ok) return;
  let done = 0;
  for (const d of devs) {
    try {
      await api("api/devices/delete", "POST", { endpointId: d.endpointId, applianceId: d.applianceId });
      done++;
    } catch (ex) { toast(`${d.name || "Gerät"}: ${ex.message}`, "err"); }
  }
  S.devSel = new Set();
  S.devices = await api("api/devices");
  render();
  toast(`${done} von ${devs.length} Geräten gelöscht (sofern sie nicht vom Skill neu erkannt werden).`);
}



function openDevice(d) {
  const [rl] = reachLabel(d);
  const det = d.details || {};
  const cv = det.legacyAppliance || {};
  openDrawer(d.name || "Gerät", `
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px">
      <span class="chip ${reachLabel(d)[1]}"><span class="dot"></span>${rl}</span>
      <span class="chip ${d.enabled ? "ok" : "err"}">${d.enabled ? "Aktiviert" : "Deaktiviert"}</span>
      ${d.skill ? `<span class="chip">Skill: ${esc(d.skill)}</span>` : ""}
    </div>
    <div class="kv">
      <span class="k">Kategorie</span><span class="v">${esc(d.category || "–")}</span>
      <span class="k">Hersteller</span><span class="v">${esc(d.manufacturer || "–")}</span>
      <span class="k">Modell</span><span class="v">${esc(cv.modelName || d.model || "–")}</span>
      <span class="k">Beschreibung</span><span class="v">${esc(cv.friendlyDescription || "–")}</span>
      <span class="k">Gruppen</span><span class="v">${(d.groups || []).map(esc).join(", ") || "–"}</span>
      <span class="k">Endpoint-ID</span><span class="v">${esc(d.endpointId || "–")}</span>
      <span class="k">Appliance-ID</span><span class="v">${esc(d.applianceId || "–")}</span>
    </div>
    <div class="actions">
      <button class="btn small ${d.enabled ? "secondary" : ""}" id="actEnable" title="${d.enabled ? "Gerät deaktivieren" : "Gerät aktivieren"}">${ic("power", 15)}<span>${d.enabled ? "Deaktivieren" : "Aktivieren"}</span></button>
      <button class="btn small secondary" id="actRename" title="Gerät umbenennen">${ic("edit", 15)}<span>Umbenennen</span></button>
      <button class="btn small danger secondary" id="actDelete" title="Gerät aus der Alexa-Liste löschen">${ic("trash", 15)}<span>Löschen</span></button>
    </div>
    <details class="raw"><summary>Details (rohe Daten)</summary><pre class="rawjson">${esc(JSON.stringify(det, null, 2))}</pre></details>
  `);
  $("#actEnable").onclick = async () => {
    if (!(d.endpointId)) return toast("Gerät hat keine Endpoint-ID.", "err");
    const ok = await confirmDialog("Gerät " + (d.enabled ? "deaktivieren" : "aktivieren") + "?",
      `„${esc(d.name)}" wird ${d.enabled ? "deaktiviert" : "aktiviert"} (in Amazon).`);
    if (!ok) return;
    try {
      await api("api/devices/enable", "POST", { endpointId: d.endpointId, enabled: !d.enabled });
      toast(`Gerät ${d.enabled ? "deaktiviert" : "aktiviert"}.`);
      S.devices = await api("api/devices");
      closeDrawer();
    } catch (ex) { toast(ex.message, "err"); }
  };
  $("#actRename").onclick = () => {
    const root = openDialog(
      "Gerät umbenennen",
      `<label class="field"><span class="lbl">Neuer Name</span>
       <input type="text" id="rnName" maxlength="80" value="${esc(d.name || "")}"></label>`,
      `<button class="btn secondary" data-act="no">Abbrechen</button>
       <button class="btn" data-act="yes">${ic("check", 16)}<span>Speichern</span></button>`
    );
    $("#rnName", root).focus();
    root.querySelector('[data-act=no]').onclick = closeDialog;
    root.querySelector('[data-act=yes]').onclick = async () => {
      const name = $("#rnName", root).value.trim();
      if (!name) return;
      try {
        await api("api/devices/rename", "POST", { endpointId: d.endpointId, name });
        toast("Umbenannt.");
        closeDialog();
        S.devices = await api("api/devices");
        closeDrawer();
      } catch (ex) { toast(ex.message, "err"); }
    };
  };
  $("#actDelete").onclick = async () => {
    const ok = await deleteConfirm("Gerät löschen", d.name || "das Gerät");
    if (!ok) return;
    try {
      await api("api/devices/delete", "POST", { endpointId: d.endpointId, applianceId: d.applianceId });
      toast("Gerät gelöscht (sofern nicht vom Skill neu erkannt wird).");
      S.devices = await api("api/devices");
      closeDrawer();
      if (S.tab === "devices") render();
    } catch (ex) { toast(ex.message, "err"); }
  };
}

// ---------------------------------------------------------------------------
// Routinen
// ---------------------------------------------------------------------------
function flattenSequence(seq) {
  if (!seq || typeof seq !== "object") return [];
  let start = seq.startNode !== undefined ? seq.startNode : seq;
  if (typeof start === "object" && start && /Serial|Parallel/.test(start["@type"] || "")) {
    return (start.nodesToExecute || []).flatMap(flattenSequence);
  }
  return [start];
}

function decodeTrigger(t) {
  if (!t) return { label: "Unbekannt", type: "Unbekannt" };
  const p = parseMaybe(t.payload);
  if (t.type === "CustomUtterance") return { label: `„${p?.utterance || "?"}"`, type: "Sprachbefehl" };
  if (t.type === "AbsoluteTimeSchedule" || t.type === "TimeWindow") {
    const sch = p?.schedule;
    if (sch) {
      const tt = String(sch.triggerTime || "");
      const time = tt.length >= 4 ? `${tt.slice(0, 2)}:${tt.slice(2, 4)}` : tt;
      const byday = /BYDAY=([A-Z,]+)/.exec(sch.recurrence || "")?.[1]?.split(",") || [];
      const when = byday.length ? byday.map((d) => DAY_DE[d] || d).join(", ") : "Täglich";
      return { label: `${when} um ${time}`, type: "Zeitplan" };
    }
  }
  return { label: t.type || "Unbekannt", type: t.type || "Unbekannt" };
}

function decodeAction(node) {
  if (!node || typeof node !== "object") return { type: "?", detail: "" };
  const at = node["@type"] || "";
  if (at.endsWith("OpaquePayloadOperationNode")) {
    const op = node.operationPayload || {};
    let detail = "";
    if (node.type === "Alexa.TextCommand") detail = `„${op.text || ""}"${op.deviceSerialNumber ? ` → ${op.deviceSerialNumber}` : ""}`;
    else if (node.type === "Alexa.SmartHome.Batch") detail = `${(op.entityIds || []).length} Gerät(e) · ${op.deviceOperation || "?"}`;
    else if (node.type === "AlexaAnnouncement") detail = `„${op.message || ""}"`;
    else if (node.type === "Alexa.System.Wait") detail = "Wartezeit";
    if (!detail) detail = JSON.stringify(op).slice(0, 140);
    return { type: node.type || at, detail };
  }
  return { type: at.split(".").pop() || at, detail: "" };
}

function routineRowsHtml(list) {
  if (!list.length) {
    return `<tr><td colspan="4"><div class="empty"><div class="big">${ic("routines", 40)}</div>Keine Routinen vorhanden.</div></td></tr>`;
  }
  return list.map((r) => {
    const t = decodeTrigger(r.triggers?.[0]);
    const acts = flattenSequence(r.sequence).length;
    const on = r.status === "ENABLED";
    return `<tr class="clickable" data-id="${esc(r.automationId)}">
      <td class="c-name">${esc(r.name || "Ohne Name")}</td>
      <td class="c-desc"><span title="${esc(t.type)}">${esc(t.label)}</span></td>
      <td><span class="badge">${acts}</span></td>
      <td class="right"><div class="row-actions">
        <button class="row-btn" data-act="run" title="Ausführen">${ic("play", 15)}</button>
        <button class="row-btn" data-act="toggle" title="${on ? "Deaktivieren" : "Aktivieren"}">${ic("power", 15)}</button>
        <button class="row-btn danger" data-act="del" title="Löschen">${ic("trash", 15)}</button>
      </div></td>
    </tr>`;
  }).join("");
}

function bindRoutineRows(c) {
  c.querySelectorAll("tr[data-id]").forEach((tr) => {
    const id = tr.dataset.id;
    tr.onclick = () => routineDrawer(id);
    const run = tr.querySelector('[data-act="run"]');
    if (run) run.onclick = (e) => { e.stopPropagation(); runRoutine(id); };
    const tog = tr.querySelector('[data-act="toggle"]');
    if (tog) tog.onclick = async (e) => {
      e.stopPropagation();
      const r = S.routines.find((x) => x.automationId === id);
      if (!r) return;
      const enabled = r.status !== "ENABLED";
      const ok = await confirmDialog("Routine " + (enabled ? "aktivieren" : "deaktivieren") + "?",
        `„${esc(r.name || "")}" wird ${enabled ? "aktiviert" : "deaktiviert"}.`);
      if (!ok) return;
      try {
        await api(`api/routines/${encodeURIComponent(id)}`, "PUT", { status: enabled ? "ENABLED" : "DISABLED" });
        toast(`Routine ${enabled ? "aktiviert" : "deaktiviert"}.`);
        S.routines = await api("api/routines");
        applyRoutineFilter(c);
      } catch (ex) { toast(ex.message, "err"); }
    };
    const del = tr.querySelector('[data-act="del"]');
    if (del) del.onclick = async (e) => {
      e.stopPropagation();
      const r = S.routines.find((x) => x.automationId === id);
      if (!r) return;
      const ok = await deleteConfirm("Routine löschen", r.name || "die Routine");
      if (!ok) return;
      try {
        const res = await api(`api/routines/${encodeURIComponent(id)}`, "DELETE");
        if (res.deleted) toast("Routine gelöscht.");
        else toast("Amazon meldete Erfolg, aber die Routine ist noch in der Liste – bitte neu laden.", "err");
        S.routines = await api("api/routines");
        applyRoutineFilter(c);
      } catch (ex) { toast(ex.message, "err"); }
    };
  });
}

function applyRoutineFilter(c) {
  const q = S.search.toLowerCase();
  const list = q ? S.routines.filter((r) =>
    (r.name + " " + JSON.stringify(r.triggers || [])).toLowerCase().includes(q)) : S.routines;
  const tb = c.querySelector("table.list tbody");
  if (!tb) return;
  tb.innerHTML = routineRowsHtml(list);
  bindRoutineRows(c);
}

function runRoutine(automationId) {
  const echoP = S.account?.echoes
    ? Promise.resolve(S.account.echoes)
    : api("api/account").then((a) => { S.account = a; return a.echoes; });
  echoP.then((echoes) => {
    const root = openDialog("Routine ausführen",
      `<label class="field"><span class="lbl">Ziel-Echo</span>
       <select id="runEcho">${echoes.map((e) => `<option value="${esc(e.serialNumber)}">${esc(e.name)}</option>`).join("")}</select></label>
       <div class="hint">Die Routinen-Sequenz wird als „Vorschau" auf dem gewählten Echo ausgeführt.</div>`,
      `<button class="btn secondary" data-act="no">Abbrechen</button>
       <button class="btn" data-act="yes">${ic("play", 16)}<span>Ausführen</span></button>`);
    root.querySelector('[data-act=no]').onclick = closeDialog;
    root.querySelector('[data-act=yes]').onclick = async () => {
      try {
        await api(`api/routines/${encodeURIComponent(automationId)}/run`, "POST",
          { serialNumber: $("#runEcho", root).value });
        toast("Routine ausgeführt.");
        closeDialog();
      } catch (ex) { toast(ex.message, "err"); }
    };
  }).catch((ex) => toast(ex.message, "err"));
}

async function renderRoutines(c) {
  if (!S.routines.length) S.routines = await api("api/routines");
  c.innerHTML = `
    <div class="page-head"><div class="spacer"></div>
      <div class="actions"><button class="btn secondary small" id="rtRefresh">${ic("refresh", 16)}<span>Neu laden</span></button></div>
    </div>
    <div class="search">${ic("search", 18)}<input id="rtSearch" placeholder="Routine suchen …" value="${esc(S.search)}"><button class="search-clear" id="rtClear" title="Filter löschen" ${S.search ? "" : "hidden"}>${ic("close", 14)}</button></div>
    <div class="card table-card">
      <table class="list compact"><thead>
      <tr>
        <th>Name</th>
        <th>Trigger</th>
        <th>Aktionen</th>
        <th class="right">Steuerung</th>
      </tr>
      </thead><tbody>
      ${routineRowsHtml(S.routines)}
      </tbody></table>
    </div>`;
  $("#rtRefresh").onclick = async () => { S.routines = await api("api/routines"); render(); };
  $("#rtSearch").oninput = (e) => {
    S.search = e.target.value;
    $("#rtClear").hidden = !S.search;
    applyRoutineFilter(c);
  };
  $("#rtClear").onclick = () => {
    S.search = "";
    $("#rtSearch").value = "";
    $("#rtClear").hidden = true;
    applyRoutineFilter(c);
  };
  bindRoutineRows(c);
}

async function routineDrawer(automationId) {
  let r;
  try { r = await api(`api/routines/${encodeURIComponent(automationId)}`); }
  catch (ex) { return toast(ex.message, "err"); }
  const t = decodeTrigger(r.triggers?.[0]);
  const nodes = flattenSequence(r.sequence);
  openDrawer(r.name || "Routine", `
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px">
      <span class="chip ${r.status === "ENABLED" ? "ok" : "err"}"><span class="dot"></span>${r.status === "ENABLED" ? "Aktiv" : "Inaktiv"}</span>
      <span class="chip">${esc(t.type)}</span>
    </div>
    <div class="kv">
      <span class="k">Name</span><span class="v">${esc(r.name || "–")}</span>
      <span class="k">Beschreibung</span><span class="v">${esc(r.description || "–")}</span>
      <span class="k">Trigger</span><span class="v">${esc(t.label)}</span>
      <span class="k">Automation-ID</span><span class="v">${esc(automationId)}</span>
    </div>
    <h2 style="font-size:14px;margin:16px 0 8px">Aktionen</h2>
    ${nodes.map((n, i) => {
      const a = decodeAction(n);
      return `<div class="chip" style="display:flex;width:100%;justify-content:space-between;margin-bottom:6px;background:var(--chip-bg)">
        <span><b>${esc(a.type)}</b>${a.detail ? " · " + esc(a.detail) : ""}</span>
      </div>`;
    }).join("") || `<div class="hint">Keine Aktionen.</div>`}
    <div class="actions">
      <button class="btn small" id="rtRun">${ic("play", 15)}<span>Ausführen</span></button>
      <button class="btn small ${r.status === "ENABLED" ? "secondary" : ""}" id="rtToggle">${ic("power", 15)}<span>${r.status === "ENABLED" ? "Deaktivieren" : "Aktivieren"}</span></button>
      <button class="btn small danger secondary" id="rtDel">${ic("trash", 15)}<span>Löschen</span></button>
    </div>
    <details class="raw"><summary>Details (rohe Routine)</summary><pre class="rawjson">${esc(JSON.stringify(r, null, 2))}</pre></details>
  `);
  $("#rtRun").onclick = () => runRoutine(automationId);
  $("#rtToggle").onclick = async () => {
    const enabled = r.status !== "ENABLED";
    const ok = await confirmDialog("Routine " + (enabled ? "aktivieren" : "deaktivieren") + "?",
      `„${esc(r.name)}" wird ${enabled ? "aktiviert" : "deaktiviert"}.`);
    if (!ok) return;
    try {
      await api(`api/routines/${encodeURIComponent(automationId)}`, "PUT", { status: enabled ? "ENABLED" : "DISABLED" });
      toast(`Routine ${enabled ? "aktiviert" : "deaktiviert"}.`);
      S.routines = await api("api/routines");
      routineDrawer(automationId);
    } catch (ex) { toast(ex.message, "err"); }
  };
  $("#rtDel").onclick = async () => {
    const ok = await deleteConfirm("Routine löschen", r.name || "die Routine");
    if (!ok) return;
    try {
      const res = await api(`api/routines/${encodeURIComponent(automationId)}`, "DELETE");
      if (res.deleted) toast("Routine gelöscht.");
      else toast("Amazon meldete Erfolg, aber die Routine ist noch in der Liste – bitte neu laden.", "err");
      S.routines = await api("api/routines");
      closeDrawer();
      if (S.tab === "routines") render();
    } catch (ex) { toast(ex.message, "err"); }
  };
}

// ---------------------------------------------------------------------------
// Einstellungen (Login)
// ---------------------------------------------------------------------------
async function renderSettings(c) {
  S.status = await refreshStatus();
  const st = S.status || { state: "none" };
  c.innerHTML = `
    <div class="page-head"><div class="spacer"></div>
      <div class="actions"><span class="chip">Version ${esc(S.status?.version || "unbekannt")}</span></div>
    </div>
    <div class="notice">
      ${ic("warning", 16)} <b>Hinweis:</b> Der Zugriff auf Alexa erfolgt über die <b>inoffizielle</b> Amazon-Web-API (derselben, die auch die Alexa-App nutzt).
      Amazon kann Endpunkte ändern – der Add-on muss dann ggf. aktualisiert werden. Es wird <b>kein Passwort gespeichert</b>,
      nur der Refresh-Token und Cookies in <code>/data</code> (Rechte 0600). Die Sitzung wird automatisch erneuert.
    </div>
    <div id="loginArea"></div>
    <div class="card">
      <h2>Theme</h2>
      <div class="filter-row" id="themeRow">
        <button class="filter" data-th="auto">System</button>
        <button class="filter" data-th="light">Hell</button>
        <button class="filter" data-th="dark">Dunkel</button>
      </div>
    </div>`;
  renderLoginArea();
  const mode = localStorage.getItem("am_theme") || "auto";
  applyTheme(mode);
  c.querySelectorAll("#themeRow [data-th]").forEach((b) => {
    if (b.dataset.th === mode) b.classList.add("active");
    b.onclick = () => {
      localStorage.setItem("am_theme", b.dataset.th);
      applyTheme(b.dataset.th);
      c.querySelectorAll("#themeRow [data-th]").forEach((x) => x.classList.toggle("active", x === b));
    };
  });

  async function renderLoginArea() {
    const area = $("#loginArea");
    if (!area) return;
    if (st.state === "ready") {
      area.innerHTML = `
        <div class="card">
          <h2>Amazon-Konto</h2>
          <div class="kv">
            <span class="k">Status</span><span class="v"><span class="chip ok"><span class="dot"></span>Verbunden</span></span>
            <span class="k">Konto</span><span class="v">${esc(st.email || "")}</span>
            <span class="k">Domain</span><span class="v">${esc(st.domain || "amazon.de")}</span>
            <span class="k">Token gespeichert</span><span class="v">${st.sessionSaved ? new Date((st.sessionSavedAt || 0) * 1000).toLocaleString("de-DE") : "nein"}</span>
          </div>
          <div class="actions">
            <button class="btn small" id="logoutBtn">${ic("power", 15)}<span>Abmelden</span></button>
          </div>
        </div>`;
      $("#logoutBtn").onclick = async () => {
        if (!(await confirmDialog("Abmelden?", "Die Amazon-Sitzung wird beendet und der gespeicherte Refresh-Token gelöscht."))) return;
        await api("api/logout", "POST");
        S.status = await refreshStatus();
        toast("Abgemeldet.");
        renderSettings(c);
      };
      return;
    }
    if (st.state === "needs_2fa") {
      area.innerHTML = `
        <div class="card">
          <h2>2-Faktor-Code</h2>
          <div class="notice">Amazon verlangt einen Bestätigungscode (${esc(st.detail || "")})</div>
          <label class="field"><span class="lbl">Code aus der Amazon-App / per E-Mail/SMS</span>
            <input type="text" id="mfaCode" inputmode="numeric" autocomplete="one-time-code" maxlength="10"></label>
          <button class="btn" id="mfaSubmit">${ic("check", 16)}<span>Code übermitteln</span></button>
        </div>`;
      const inp = $("#mfaCode");
      inp.focus();
      inp.onkeydown = (e) => { if (e.key === "Enter") submitMfa(); };
      $("#mfaSubmit").onclick = submitMfa;
      async function submitMfa() {
        const code = inp.value.trim();
        if (code.length < 4) return toast("Code zu kurz.", "err");
        try {
          S.status = await api("api/login/code", "POST", { code });
          updateSessionChip();
          toast(S.status.state === "ready" ? "Erfolgreich angemeldet." : "Code übernommen …");
          if (S.status.state !== "ready") renderSettings(c);
          else go("overview");
        } catch (ex) { toast(ex.message, "err"); S.status = await refreshStatus(); renderSettings(c); }
      }
      return;
    }
    if (st.state === "needs_option") {
      const opts = st.options?.options || {};
      const entries = Object.entries(opts);
      area.innerHTML = `
        <div class="card">
          <h2>Auswahl erforderlich</h2>
          <div class="notice">${esc(st.detail || "")}</div>
          ${entries.map(([k, v]) => `<label class="checkbox-row"><input type="radio" name="opt" value="${esc(k)}">
            <span>${esc(v)}</span></label>`).join("") || `<div class="hint">Optionen: ${esc(JSON.stringify(opts))}</div>`}
          <div class="actions"><button class="btn" id="optSubmit">${ic("check", 16)}<span>Übernehmen</span></button></div>
        </div>`;
      $("#optSubmit").onclick = async () => {
        const sel = area.querySelector('input[name=opt]:checked');
        if (!sel) return toast("Bitte Option wählen.", "err");
        try {
          S.status = await api("api/login/option", "POST", { option: sel.value });
          updateSessionChip();
          toast("Auswahl übernommen …");
          if (S.status.state !== "ready") renderSettings(c);
          else go("overview");
        } catch (ex) { toast(ex.message, "err"); S.status = await refreshStatus(); renderSettings(c); }
      };
      return;
    }
    // none | error | working
    const proxyWait = !!st.proxyActive && st.state !== "ready";
    area.innerHTML = `
      <div class="card">
        <h2>Amazon verbinden</h2>
        ${st.state === "error" ? `<div class="notice err">${esc(st.detail || "Login fehlgeschlagen.")}</div>` : ""}
        ${st.state === "working" ? `<div class="notice">${esc(st.detail || "Bitte warten …")}</div>` : ""}
        <div class="notice">${ic("alexa", 16)} <b>Empfohlen: Browser-Login.</b> Du meldest dich im neuen Tab ganz normal bei Amazon an
        (E-Mail, Passwort, 2FA-Code aus der Authenticator-App). Danach holt sich der Add-on alles automatisch –
        es wird kein Passwort gespeichert, nur Refresh-Token + Cookies.</div>
        <button class="btn" id="browserLoginBtn">${ic("check", 16)}<span>${proxyWait ? "Amazon-Login im Browser (Tab erneut oeffnen)" : "Amazon-Login im Browser starten"}</span></button>
        ${proxyWait ? `<div class="hint" style="margin-top:8px"><b>Warte auf die Anmeldung im Browser …</b> Bitte im ge&ouml;ffneten Tab bei Amazon anmelden (E-Mail, Passwort, 2FA-Code). Der Status aktualisiert sich von selbst.</div>` : ""}
        ${(() => {
          const pr = st.proxy;
          if (!pr || st.state === "ready") return "";
          const line = pr.active
            ? "Browser-Login laeuft noch …"
            : (pr.hasCode ? "Code erkannt – Finalisierung laeuft …"
              : "Anmeldung im Tab war abgeschlossen, aber es wurde <b>kein</b> Autorisierungs-Code gefangen. Bitte 'Amazon-Login im Browser starten' erneut klicken und sauber durchmelden.");
          return `<details style="margin-top:10px"><summary class="hint" style="cursor:pointer">Diagnose (Proxy-Status) – bei Problemen aufklappen und melden</summary>
            <div class="hint" style="margin-top:6px">${line}</div>
            <div class="hint" style="margin-top:4px">Cookies (${pr.cookieCount}): ${esc(pr.cookieNames ? pr.cookieNames.join(", ") : "–")}</div>
            ${pr.lastEvent ? `<div class="hint" style="margin-top:4px;word-break:break-all">Letzter Schritt: ${esc(pr.lastEvent)}</div>` : ""}
            ${(pr.events && pr.events.length) ? `<div class="hint" style="margin-top:6px"><b>Schritte:</b></div><pre style="margin:4px 0 0;padding:8px;background:var(--ha-card-background,rgba(128,128,128,.08));border-radius:6px;max-height:260px;overflow:auto;font-size:11px;white-space:pre-wrap;word-break:break-all">${esc(pr.events.join("\n"))}</pre>` : ""}
          </details>`;
        })()}
        <details style="margin-top:14px">
          <summary class="hint" style="cursor:pointer">Alternative: E-Mail + Passwort direkt im Add-on (kommt bei manchen Konten nicht durch)</summary>
          <div style="margin-top:10px">
          <label class="field"><span class="lbl">Amazon E-Mail</span>
            <input type="email" id="amEmail" autocomplete="username" value="${esc(st.email || "")}"></label>
          <label class="field"><span class="lbl">Passwort</span>
            <input type="password" id="amPass" autocomplete="current-password"></label>
          <label class="field"><span class="lbl">Domain (Standard: amazon.de)</span>
            <input type="text" id="amDomain" value="${esc(st.domain || "amazon.de")}"></label>
          <button class="btn" id="loginBtn">${ic("check", 16)}<span>Anmelden</span></button>
          <div class="hint" style="margin-top:8px">Das Passwort wird nicht gespeichert. Nach dem Login genügt der Refresh-Token – er wird automatisch erneuert.</div>
          </div>
        </details>
      </div>`;
    $("#browserLoginBtn").onclick = startBrowserLogin;
    function stopProxyPoll() {
      if (S._proxyPoll) { clearInterval(S._proxyPoll); S._proxyPoll = null; }
    }
    async function startBrowserLogin() {
      const btn = $("#browserLoginBtn");
      btn.disabled = true;
      try {
        const r = await api("api/proxy/login/start", "POST", {});
        const win = window.open(r.url, "_blank");
        toast("Bitte im neuen Tab bei Amazon anmelden …");
        if (S._proxyPoll) stopProxyPoll();
        S._lastSig = null;
        let closed = false, fast = 0;
        const tick = async () => {
          try {
            // Login-Fenster wurde geschlossen -> sofort + schneller aktualisieren
            if (win && win.closed && !closed) {
              closed = true;
              toast("Login-Fenster geschlossen – Status wird aktualisiert …");
              if (S._proxyPoll) { clearInterval(S._proxyPoll); S._proxyPoll = null; }
              S._proxyPoll = setInterval(tick, 500);
            }
            S.status = await refreshStatus();
            const s = S.status;
            if (s.state === "ready") {
              stopProxyPoll();
              toast("Erfolgreich angemeldet.");
              go("overview");
              return;
            }
            if (s.state === "error") {
              stopProxyPoll();
              renderSettings(c);
              return;
            }
            const evs = (s.proxy && s.proxy.events) || [];
            const sig = s.state + ":" + !!s.proxyActive + ":" + evs.length;
            if (sig !== S._lastSig) {
              S._lastSig = sig;
              renderSettings(c);
            }
            // Nach Fenster-Schluess: ~15 s Schnell-Polling, dann stoppen
            if (closed && ++fast >= 30) stopProxyPoll();
          } catch { /* Polling-Fehler ignorieren */ }
        };
        S._proxyPoll = setInterval(tick, 2500);
        tick();
      } catch (ex) {
        toast(ex.message, "err");
        btn.disabled = false;
      }
    }
    $("#loginBtn").onclick = async () => {
      const email = $("#amEmail").value.trim();
      const pass = $("#amPass").value;
      if (!email || !pass) return toast("E-Mail und Passwort erforderlich.", "err");
      const btn = $("#loginBtn");
      btn.disabled = true;
      btn.innerHTML = `${ic("refresh", 15)}<span>Amazon wird kontaktiert …</span>`;
      try {
        S.status = await api("api/login", "POST", { email, password: pass, domain: $("#amDomain").value.trim() });
        updateSessionChip();
        if (S.status.state === "ready") { toast("Erfolgreich angemeldet."); go("overview"); }
        else renderSettings(c);
      } catch (ex) {
        toast(ex.message, "err");
        S.status = await refreshStatus();
        renderSettings(c);
      }
    };
    $("#amPass").focus();
  }
}

// ---------------------------------------------------------------------------
// Theme
// ---------------------------------------------------------------------------
function parseLum(v) {
  // Helligkeit 0..1 aus "#rrggbb", "#rgb" oder "rgb()/rgba()" - sonst null.
  if (!v) return null;
  let r, g, b;
  const m = String(v).match(/rgba?\(\s*(\d+)[\s,]+(\d+)[\s,]+(\d+)/);
  if (m) { r = +m[1]; g = +m[2]; b = +m[3]; }
  else {
    let h = String(v).replace(/^#/, "").trim();
    if (h.length === 3) h = h.split("").map((c) => c + c).join("");
    if (h.length < 6) return null;
    r = parseInt(h.slice(0, 2), 16);
    g = parseInt(h.slice(2, 4), 16);
    b = parseInt(h.slice(4, 6), 16);
    if ([r, g, b].some((x) => Number.isNaN(x))) return null;
  }
  return (0.299 * r + 0.587 * g + 0.114 * b) / 255;
}

function haThemeVars() {
  // HA-Theme-Variablen 1:1 uebernehmen. Kandidaten:
  //   Doku: Parent (Panel laeuft im HA-iFrame, gleiche Origin) + eigene Doku
  //   (inline gerendert = dieselbe Doku wie HA).
  //   Elemente: body, ha-theme, ha-app, home-assistant, html.
  const docs = [];
  try {
    const p = window.parent;
    if (p && p !== window && p.document) docs.push(p.document);
  } catch { /* Parent nicht lesbar */ }
  docs.push(document);
  const sels = ["body", "ha-theme", "ha-app", "home-assistant", "html"];
  for (const doc of docs) {
    for (const s of sels) {
      const el = s === "html" ? doc.documentElement : doc.querySelector(s);
      if (!el) continue;
      const cs = getComputedStyle(el);
      const get = (a) => cs.getPropertyValue(a).trim();
      const out = {
        bg: get("--primary-background-color"),
        card: get("--card-background-color") || get("--primary-surface-color"),
        line: get("--divider-color"),
        text: get("--primary-text-color"),
        text2: get("--secondary-text-color"),
        primary: get("--primary-color"),
      };
      if (Object.values(out).some(Boolean)) return out;
    }
  }
  return null;
}

const THEME_OVERRIDES = ["--bg", "--card", "--line", "--text", "--text-2", "--primary"];

function applyTheme(mode) {
  const root = document.documentElement;
  const tv = haThemeVars();
  let dark, adopt = false;
  if (mode === "auto") {
    const lum = parseLum(tv ? tv.bg : "");
    dark = lum != null ? lum < 0.5
      : window.matchMedia("(prefers-color-scheme: dark)").matches;
    adopt = !!tv;
  } else {
    dark = mode === "dark";
    // Manueller Modus: HA-Farben ebenfalls 1:1 uebernehmen, sobald sie
    // vorhanden sind UND zur gewaehlten Helligkeit passen (HA dunkel +
    // "Dunkel" -> HA-schwarz statt eigene blaue Palette).
    const lum = parseLum(tv ? tv.bg : "");
    adopt = !!(tv && lum != null && (lum < 0.5) === dark);
  }
  root.setAttribute("data-theme", dark ? "dark" : "light");
  if (adopt) {
    if (tv.bg) root.style.setProperty("--bg", tv.bg);
    if (tv.card) root.style.setProperty("--card", tv.card);
    if (tv.line) root.style.setProperty("--line", tv.line);
    if (tv.text) root.style.setProperty("--text", tv.text);
    if (tv.text2) root.style.setProperty("--text-2", tv.text2);
    if (tv.primary) root.style.setProperty("--primary", tv.primary);
  } else {
    THEME_OVERRIDES.forEach((k) => root.style.removeProperty(k));
  }
  $("#themeBtn").innerHTML = ic(dark ? "light" : "power", 18);
}
$("#themeBtn").onclick = () => {
  const cur = document.documentElement.getAttribute("data-theme");
  const mode = cur === "dark" ? "light" : "dark";
  localStorage.setItem("am_theme", mode);
  applyTheme(mode);
};
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
  if ((localStorage.getItem("am_theme") || "auto") === "auto") applyTheme("auto");
});
// HA-Theme laeuft im Parent (gleiche Origin): bei Aenderungen (Theme-Wechsel
// in HA) den aktuellen Modus neu anwenden.
try {
  const p = window.parent;
  if (p && p !== window && p.document && p.document.documentElement) {
    const ob = new MutationObserver(() => {
      applyTheme(localStorage.getItem("am_theme") || "auto");
    });
    ob.observe(p.document.documentElement, {
      attributes: true, attributeFilter: ["class", "style", "color-scheme", "data-theme"],
      subtree: true,
    });
  }
} catch { /* Parent nicht lesbar */ }

// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------
async function init() {
  renderTabs();
  await refreshStatus();
  render();
  // HA-Theme-Variablen sind beim Panelstart evtl. noch nicht da (Timing,
  // Parent rendert spaeter). Ein paar Mal probieren; sobald vorhanden,
  // aktuellen Modus neu anwenden (Farben uebernehmen).
  const mode = localStorage.getItem("am_theme") || "auto";
  let tries = 0;
  const retry = () => {
    tries += 1;
    const tv = haThemeVars();
    if (tv) { applyTheme(mode); return; }
    if (tries < 5) setTimeout(retry, 1500);
  };
  retry();
}
init();
})();
