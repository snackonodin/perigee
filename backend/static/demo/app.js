/* Astronaut Health Monitor: offline demo page. Vanilla JS, same origin, no CDN.
 *
 * Rules kept here:
 * - Server data is rendered with textContent / DOM APIs only, never parsed as HTML.
 * - The safety screen is shown BEFORE anything else whenever safety.show is set, and also
 *   from a local pre-check of the instrument's safety_trigger items, so a slow or failed
 *   request can never hide it.
 * - Tokens live in sessionStorage (cleared when the tab closes).
 */
"use strict";

// Every API path the page calls. tests/api/test_demo_page.py checks each one exists in
// /openapi.json, so keep them as literal templates here.
const PATHS = {
  signup: "/api/v1/auth/signup",
  login: "/api/v1/auth/login",
  refresh: "/api/v1/auth/refresh",
  logout: "/api/v1/auth/logout",
  me: "/api/v1/me",
  today: "/api/v1/today",
  nights: "/api/v1/nights",
  instrument: "/api/v1/instruments/{instrument_id}",
  responses: "/api/v1/responses",
};

// Fallback copy of seeds/safety_resources.json, used only if the server cannot be reached
// after a local safety trigger. A test keeps it identical to the seed file.
const SAFETY_FALLBACK = {
  reason:
    "You indicated thoughts of being better off dead or of hurting yourself. You do not have to handle this alone.",
  resources: [
    "Contact your flight surgeon or your designated support contact now.",
    "If you are in immediate danger, call your local emergency number now.",
    "If you can, stay with or reach out to someone you trust while you get support.",
  ],
};

const TREND_DAYS = 28;
const SLOT_LABEL = { am: "Morning", pm: "Evening" };
const STATE_LABEL = {
  both: "Body and mood both differ from your usual",
  phys_only: "Your sleep breathing differs from your usual",
  mental_only: "Your check-ins differ from your usual",
};
const MATURITY_LABEL = { warm_up: "warming up", widening: "widening", mature: "mature" };

// --------------------------------------------------------------------------- tiny helpers

const $ = (id) => document.getElementById(id);

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === undefined || v === null || v === false) continue;
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v === true ? "" : String(v));
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return node;
}

function svg(tag, attrs = {}) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
  return node;
}

function fmt(v, digits = 1) {
  return typeof v === "number" && Number.isFinite(v) ? v.toFixed(digits) : "–";
}

function isoDay(d) {
  return d.toISOString().slice(0, 10);
}

function store(key, value) {
  try {
    if (value === null) sessionStorage.removeItem(key);
    else sessionStorage.setItem(key, value);
  } catch (_) {
    /* private mode: keep working without persistence */
  }
}

function load(key) {
  try {
    return sessionStorage.getItem(key);
  } catch (_) {
    return null;
  }
}

function show(screen) {
  for (const s of document.querySelectorAll(".screen")) s.hidden = s.id !== `screen-${screen}`;
  $("logout-btn").hidden = screen === "login";
}

// --------------------------------------------------------------------------- API client

class ApiError extends Error {
  constructor(status, body, retryAfter) {
    super((body && body.message) || `request failed (${status})`);
    this.status = status;
    this.body = body;
    this.retryAfter = retryAfter;
  }
}

const auth = {
  get access() {
    return load("ahm.access");
  },
  get refresh() {
    return load("ahm.refresh");
  },
  set(tokens) {
    store("ahm.access", tokens.access_token);
    store("ahm.refresh", tokens.refresh_token);
  },
  clear() {
    store("ahm.access", null);
    store("ahm.refresh", null);
  },
};

async function api(method, path, { body, query, retry = true } = {}) {
  let url = path;
  if (query) url += "?" + new URLSearchParams(query).toString();
  const headers = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth.access) headers.Authorization = `Bearer ${auth.access}`;
  const res = await fetch(url, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (res.status === 401 && retry && auth.refresh && path !== PATHS.refresh) {
    if (await refreshTokens()) return api(method, path, { body, query, retry: false });
  }
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch (_) {
    data = null;
  }
  if (!res.ok) throw new ApiError(res.status, data, res.headers.get("Retry-After"));
  return data;
}

async function refreshTokens() {
  try {
    const t = await api("POST", PATHS.refresh, {
      body: { refresh_token: auth.refresh },
      retry: false,
    });
    auth.set(t);
    return true;
  } catch (_) {
    auth.clear();
    return false;
  }
}

function describeError(e) {
  if (e instanceof ApiError) {
    if (e.status === 429) {
      const mins = Math.ceil(Number(e.retryAfter || 60) / 60);
      return `Too many failed sign-ins. Try again in about ${mins} minute${mins === 1 ? "" : "s"}.`;
    }
    return e.message;
  }
  return "Cannot reach the server. Is the API running?";
}

// --------------------------------------------------------------------------- personas

let personas = [];

async function loadPersonas() {
  try {
    const res = await fetch("personas.json", { headers: { Accept: "application/json" } });
    personas = res.ok ? (await res.json()).personas || [] : [];
  } catch (_) {
    personas = [];
  }
  const select = $("persona-select");
  select.replaceChildren(el("option", { value: "", text: "Choose…" }));
  for (const p of personas) select.append(el("option", { value: p.email, text: p.label || p.email }));
  $("persona-wrap").hidden = personas.length === 0;
  select.addEventListener("change", async () => {
    const email = select.value;
    if (!email) return;
    await logout({ keepPersona: true });
    $("login-email").value = email;
    const pw = load("ahm.demo_password");
    if (pw) {
      $("login-password").value = pw;
      await submitLogin(false);
    } else {
      $("login-password").focus();
    }
  });
}

function isPersona(email) {
  return personas.some((p) => p.email === email);
}

// --------------------------------------------------------------------------- login / signup

let signupMode = false;

function setSignupMode(on) {
  signupMode = on;
  $("login-title").textContent = on ? "Create an account" : "Sign in";
  $("login-submit").textContent = on ? "Create account" : "Sign in";
  $("toggle-signup").textContent = on ? "I already have an account" : "Create an account instead";
  $("login-password").autocomplete = on ? "new-password" : "current-password";
  $("login-error").textContent = "";
}

async function submitLogin(signup) {
  const email = $("login-email").value.trim();
  const password = $("login-password").value;
  const btn = $("login-submit");
  btn.disabled = true;
  $("login-error").textContent = "";
  try {
    const tokens = await api("POST", signup ? PATHS.signup : PATHS.login, {
      body: { email, password },
      retry: false,
    });
    auth.set(tokens);
    if (isPersona(email)) store("ahm.demo_password", password);
    $("login-password").value = "";
    await openToday();
  } catch (e) {
    let msg = describeError(e);
    if (e instanceof ApiError && e.status === 422 && e.body && e.body.fields) {
      msg = `Please check: ${e.body.fields.join(", ")}`;
      if (e.body.fields.includes("password")) msg += " (at least 10 characters)";
    }
    $("login-error").textContent = msg;
  } finally {
    btn.disabled = false;
  }
}

async function logout({ keepPersona = false } = {}) {
  const refresh = auth.refresh;
  auth.clear();
  if (refresh) {
    try {
      await api("POST", PATHS.logout, { body: { refresh_token: refresh }, retry: false });
    } catch (_) {
      /* already logged out server-side or offline: local tokens are gone either way */
    }
  }
  if (!keepPersona) $("persona-select").value = "";
  $("who").textContent = "";
  $("synthetic-badge").hidden = true;
  setSignupMode(false);
  show("login");
}

// --------------------------------------------------------------------------- Today

async function openToday() {
  show("today");
  $("today-error").textContent = "";
  try {
    const end = new Date();
    const start = new Date(end.getTime() - (TREND_DAYS - 1) * 86400000);
    const [me, today, nights] = await Promise.all([
      api("GET", PATHS.me),
      api("GET", PATHS.today),
      api("GET", PATHS.nights, { query: { from: isoDay(start), to: isoDay(end) } }),
    ]);
    $("who").textContent = me.display_name || me.email;
    const synthetic =
      me.is_synthetic ||
      isPersona(me.email) ||
      (today.latest_night && today.latest_night.source_kind === "synthetic") ||
      nights.some((n) => n.source_kind === "synthetic");
    $("synthetic-badge").hidden = !synthetic;
    renderNight(today.latest_night);
    renderPending(today.pending_checkins, today.checkins_consent);
    renderFlags(today.flags);
    renderBaselines(today.baselines);
    renderTrend(nights, (today.baselines || []).find((b) => b.feature === "rr_med"));
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) return logout();
    $("today-error").textContent = describeError(e);
  }
}

function renderNight(n) {
  const box = $("night");
  if (!n) {
    box.replaceChildren(el("p", { class: "muted", text: "No night recorded yet." }));
    return;
  }
  const rows = [
    ["Night of", n.date],
    ["Breathing rate (median)", `${fmt(n.rr_med)} breaths/min`],
    ["Time in bed", `${fmt(n.presence_hours)} h`],
    ["Restless", `${fmt(n.restless_frac * 100, 0)} %`],
    ["Signal quality", `${fmt(n.quality * 100, 0)} %`],
  ];
  const dl = el("dl", { class: "kv" });
  for (const [k, v] of rows) dl.append(el("dt", { text: k }), el("dd", { text: v }));
  box.replaceChildren(dl);
  if (!n.valid) {
    box.append(el("p", { class: "muted", text: "Not enough good signal: this night is not used for baselines." }));
  }
}

function renderPending(items, consent) {
  const box = $("pending");
  if (consent === false) {
    box.replaceChildren(el("p", { class: "muted", text: "Check-ins are off (consent not given)." }));
    return;
  }
  if (!items || items.length === 0) {
    box.replaceChildren(el("p", { class: "muted", text: "All done for today." }));
    return;
  }
  box.replaceChildren(
    ...items.map((p) =>
      el(
        "div",
        { class: "pending-item" },
        el("span", { text: `${SLOT_LABEL[p.slot] || p.slot} check-in` }),
        el("button", {
          type: "button",
          text: "Start",
          onclick: () => openCheckin(p.instrument_id, p.instrument_version),
        }),
      ),
    ),
  );
}

function whyTable(components) {
  const rows = [];
  for (const [domain, entries] of [
    ["Body", (components && components.physiology) || {}],
    ["Mood", (components && components.mental) || {}],
  ]) {
    for (const [name, e] of Object.entries(entries)) {
      if (!e || typeof e !== "object") continue;
      const z = typeof e.z === "number" ? e.z : null;
      const alert = components.alert_robust_z;
      let note = "";
      if (e.skipped === "warm_up") note = "baseline warming up";
      else if (e.skipped === "no_baseline") note = "no baseline yet";
      else if (e.band && e.band.band) note = `questionnaire band: ${e.band.band}`;
      rows.push(
        el(
          "tr",
          {},
          el("td", { text: domain }),
          el("td", { text: name }),
          el("td", { text: fmt(e.value, 2) }),
          el("td", { text: e.median === undefined ? "–" : `${fmt(e.median, 2)} ± ${fmt(e.mad, 2)}` }),
          el("td", {
            class: z !== null && typeof alert === "number" && Math.abs(z) >= alert ? "z-high" : "",
            text: z === null ? note || "–" : `${z >= 0 ? "+" : ""}${fmt(z, 1)}`,
          }),
        ),
      );
    }
  }
  if (rows.length === 0) return el("p", { class: "muted", text: "No details recorded." });
  return el(
    "table",
    { class: "why" },
    el(
      "thead",
      {},
      el("tr", {}, ...["", "Signal", "Value", "Your usual (median ± MAD)", "z"].map((h) => el("th", { text: h }))),
    ),
    el("tbody", {}, rows),
  );
}

function renderFlags(flags) {
  const box = $("flags");
  if (!flags || flags.length === 0) {
    box.replaceChildren(el("p", { class: "muted", text: "Nothing unusual for you in the last 7 days." }));
    return;
  }
  box.replaceChildren(
    ...flags.slice(0, 3).map((f) =>
      el(
        "div",
        { class: "flag" },
        el("div", { class: "state", text: STATE_LABEL[f.state] || f.state }),
        el("div", { class: "muted", text: `${f.date} · priority ${fmt(f.priority, 2)}` }),
        el("h3", { text: "Why" }),
        whyTable(f.components),
        (f.guidance || []).length ? el("h3", { text: "Suggestions" }) : null,
        (f.guidance || []).map((g) =>
          el(
            "div",
            { class: "guidance" },
            el("strong", { text: g.title }),
            el("p", { text: g.body }),
            g.contact_support_text ? el("p", { text: g.contact_support_text }) : null,
            el("div", {
              class: "src",
              text: `Source: ${g.source_note}${g.reviewed_by ? ` · reviewed by ${g.reviewed_by}` : " · not yet clinically reviewed"}`,
            }),
          ),
        ),
      ),
    ),
  );
}

function renderBaselines(list) {
  const box = $("baselines");
  if (!list || list.length === 0) {
    box.replaceChildren(el("p", { class: "muted", text: "Baselines start after your first valid nights." }));
    return;
  }
  const dl = el("dl", { class: "kv" });
  for (const b of list) {
    dl.append(
      el("dt", { text: b.feature }),
      el(
        "dd",
        {},
        el("span", { class: `maturity ${b.maturity}`, text: MATURITY_LABEL[b.maturity] || b.maturity }),
        ` ${b.n} nights · ${fmt(b.median, 2)} ± ${fmt(b.mad, 2)}`,
      ),
    );
  }
  box.replaceChildren(dl);
}

// Inline SVG: rr_med per night against the median ± MAD band.
function renderTrend(nights, baseline) {
  const box = $("trend");
  const pts = (nights || [])
    .filter((n) => typeof n.rr_med === "number" && n.valid)
    .map((n) => ({ t: Date.parse(n.date + "T00:00:00Z"), v: n.rr_med, d: n.date }))
    .sort((a, b) => a.t - b.t);
  if (pts.length === 0) {
    box.replaceChildren(el("p", { class: "muted", text: "No valid nights in the last 4 weeks." }));
    return;
  }
  const W = 640, H = 220, L = 40, R = 12, T = 12, B = 28;
  const end = Date.now();
  const start = end - (TREND_DAYS - 1) * 86400000;
  const med = baseline && typeof baseline.median === "number" ? baseline.median : null;
  const mad = baseline && typeof baseline.mad === "number" ? baseline.mad : null;
  const values = pts.map((p) => p.v);
  if (med !== null) values.push(med - (mad || 0), med + (mad || 0));
  let lo = Math.min(...values), hi = Math.max(...values);
  const pad = Math.max((hi - lo) * 0.15, 0.5);
  lo -= pad;
  hi += pad;
  const x = (t) => L + ((t - start) / (end - start)) * (W - L - R);
  const y = (v) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);

  const root = svg("svg", { class: "trend", viewBox: `0 0 ${W} ${H}`, role: "img" });
  root.append(svg("title"));
  root.firstChild.textContent = "Breathing rate per night against your usual range";
  if (med !== null && mad !== null) {
    root.append(svg("rect", { class: "band", x: L, width: W - L - R, y: y(med + mad), height: Math.max(y(med - mad) - y(med + mad), 1) }));
  }
  if (med !== null) {
    root.append(svg("line", { class: "median", x1: L, x2: W - R, y1: y(med), y2: y(med) }));
  }
  root.append(svg("line", { class: "axis", x1: L, x2: W - R, y1: H - B, y2: H - B }));
  for (const v of [lo + pad, (lo + hi) / 2, hi - pad]) {
    const label = svg("text", { class: "label", x: L - 6, y: y(v) + 4, "text-anchor": "end" });
    label.textContent = fmt(v, 1);
    root.append(label);
  }
  for (const t of [start, end]) {
    const label = svg("text", { class: "label", x: x(t), y: H - 8, "text-anchor": t === start ? "start" : "end" });
    label.textContent = isoDay(new Date(t));
    root.append(label);
  }
  root.append(svg("polyline", { class: "line", points: pts.map((p) => `${x(p.t)},${y(p.v)}`).join(" ") }));
  for (const p of pts) {
    const out = med !== null && mad !== null && Math.abs(p.v - med) > mad;
    const c = svg("circle", { class: out ? "pt out" : "pt", cx: x(p.t), cy: y(p.v), r: 3.5 });
    const tip = svg("title");
    tip.textContent = `${p.d}: ${fmt(p.v)} breaths/min`;
    c.append(tip);
    root.append(c);
  }
  box.replaceChildren(root);
  if (!baseline || baseline.maturity === "warm_up") {
    box.append(el("p", { class: "muted", text: "Your usual range is still warming up." }));
  }
}

// --------------------------------------------------------------------------- check-in

let currentInstrument = null;

async function openCheckin(instrumentId, version) {
  show("checkin");
  const form = $("checkin-form");
  form.replaceChildren();
  $("checkin-error").textContent = "";
  $("checkin-result").replaceChildren();
  try {
    const def = await api("GET", PATHS.instrument.replace("{instrument_id}", encodeURIComponent(instrumentId)));
    currentInstrument = { ...def, version: version || def.version };
    $("checkin-title").textContent = def.name || instrumentId;
    $("checkin-timeframe").textContent = def.timeframe || "";
    for (const item of def.items || []) {
      const fs = el("fieldset", {}, el("legend", { text: item.text }));
      for (const opt of item.options || []) {
        fs.append(
          el(
            "label",
            { class: "option" },
            el("input", { type: "radio", name: item.key, value: opt.value, required: true }),
            el("span", { text: opt.label }),
          ),
        );
      }
      form.append(fs);
    }
    form.append(el("button", { type: "submit", text: "Submit" }));
  } catch (e) {
    $("checkin-error").textContent = describeError(e);
  }
}

// Local copy of the server's rule: any answer >= an item's safety_trigger.min_value.
function localSafetyTriggered(def, answers) {
  return (def.items || []).some(
    (it) => it.safety_trigger && typeof answers[it.key] === "number" && answers[it.key] >= it.safety_trigger.min_value,
  );
}

async function submitCheckin(ev) {
  ev.preventDefault();
  const def = currentInstrument;
  if (!def) return;
  const answers = {};
  for (const item of def.items || []) {
    const checked = $("checkin-form").querySelector(`input[name="${CSS.escape(item.key)}"]:checked`);
    if (checked) answers[item.key] = Number(checked.value);
  }
  // 1) Immediate, before the network: the safety screen never waits on the server.
  if (localSafetyTriggered(def, answers)) showSafety(SAFETY_FALLBACK);

  const btn = $("checkin-form").querySelector("button[type=submit]");
  btn.disabled = true;
  let out = null;
  try {
    out = await api("POST", PATHS.responses, {
      body: { instrument_id: def.id, instrument_version: def.version, answers },
    });
  } catch (e) {
    // A 500 from /responses still carries the safety result: honour it first.
    if (e instanceof ApiError && e.body && e.body.safety) out = e.body;
    else $("checkin-error").textContent = describeError(e);
  } finally {
    btn.disabled = false;
  }
  if (!out) return;
  // 2) The server's safety result wins and is shown before any score.
  if (out.safety && out.safety.show) {
    showSafety({
      reason: out.safety.reason || SAFETY_FALLBACK.reason,
      resources: out.safety.resources && out.safety.resources.length ? out.safety.resources : SAFETY_FALLBACK.resources,
    });
  }
  renderCheckinResult(out);
}

function renderCheckinResult(out) {
  const box = $("checkin-result");
  if (!out.ok) {
    const what = out.errors && out.errors.length ? `: ${out.errors.join(", ")}` : "";
    $("checkin-error").textContent = `Not saved (${out.error || "error"})${what}.`;
    return;
  }
  $("checkin-form").replaceChildren();
  box.replaceChildren(
    el("p", { text: out.stored ? "Saved. Thank you." : "Scored, but answers not kept (consent off)." }),
    typeof out.total === "number" ? el("p", { class: "muted", text: `Total score: ${out.total}` }) : null,
    el("button", { type: "button", text: "Back to Today", onclick: openToday }),
  );
}

// --------------------------------------------------------------------------- safety screen

function showSafety({ reason, resources }) {
  $("safety-reason").textContent = reason;
  $("safety-resources").replaceChildren(...resources.map((r) => el("li", { text: r })));
  const box = $("safety");
  box.hidden = false;
  $("safety-ack").focus();
}

// --------------------------------------------------------------------------- boot

function boot() {
  $("login-form").addEventListener("submit", (ev) => {
    ev.preventDefault();
    submitLogin(signupMode);
  });
  $("toggle-signup").addEventListener("click", () => setSignupMode(!signupMode));
  $("logout-btn").addEventListener("click", () => logout());
  $("checkin-back").addEventListener("click", openToday);
  $("checkin-form").addEventListener("submit", submitCheckin);
  $("safety-ack").addEventListener("click", () => {
    $("safety").hidden = true;
  });
  loadPersonas();
  if (auth.access || auth.refresh) openToday();
  else show("login");
}

document.addEventListener("DOMContentLoaded", boot);
