const apiBase = window.RTBDI_API_BASE || localStorage.getItem("rtbdiApiBase") || "";
function newSessionId() {
  if (window.crypto && typeof window.crypto.randomUUID === "function") {
    return window.crypto.randomUUID();
  }
  return `session-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
const sessionId = localStorage.getItem("rtbdiSessionId") || newSessionId();
localStorage.setItem("rtbdiSessionId", sessionId);

const messages = document.querySelector("#messages");
const form = document.querySelector("#chatForm");
const input = document.querySelector("#question");
const connectionStatus = document.querySelector("#connectionStatus");

function formatDateRange(dateRange) {
  if (!dateRange) return "";
  if (dateRange.label) return `${dateRange.label} (${dateRange.start} to ${dateRange.end})`;
  return `${dateRange.start} to ${dateRange.end}`;
}

function pill(label, value) {
  if (!value && value !== 0) return "";
  return `<span class="pill"><strong>${label}</strong>${value}</span>`;
}

function renderMeta(meta = {}) {
  const reports = Array.isArray(meta.reports_used) && meta.reports_used.length
    ? meta.reports_used.join(", ")
    : "";
  const chips = [
    pill("Reports", reports),
    pill("Date", formatDateRange(meta.date_range)),
    pill("Rows", meta.rows_used),
    meta.memory_used ? pill("Memory", "used") : "",
  ].filter(Boolean).join("");

  const technical = {
    canonical_question: meta.canonical_question,
    reports_used: meta.reports_used,
    date_range: meta.date_range,
    rows_used: meta.rows_used,
    memory_used: meta.memory_used,
  };

  return `
    ${chips ? `<div class="meta-pills">${chips}</div>` : ""}
    <details class="technical-details">
      <summary>Technical details</summary>
      <pre>${JSON.stringify(technical, null, 2)}</pre>
    </details>
  `;
}

function addMessage(role, content, meta = {}) {
  const article = document.createElement("article");
  article.className = `message ${role}`;
  const body = document.createElement("div");
  body.className = "message-body";
  body.textContent = content;
  article.appendChild(body);
  if (Object.keys(meta).length && role.includes("assistant")) {
    const metaWrap = document.createElement("div");
    metaWrap.className = "message-meta";
    metaWrap.innerHTML = renderMeta(meta);
    article.appendChild(metaWrap);
  }
  messages.appendChild(article);
  article.scrollIntoView({ behavior: "smooth", block: "end" });
  return article;
}

async function postJson(path, payload) {
  const response = await fetch(`${apiBase}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "Request failed");
  }
  return data;
}

async function checkBackend() {
  try {
    const response = await fetch(`${apiBase}/health`);
    const data = await response.json();
    if (!response.ok) throw new Error("Backend unavailable");
    connectionStatus.textContent = `Connected to live backend (${data.browser})`;
    connectionStatus.className = "connection-status ok";
  } catch (error) {
    connectionStatus.textContent = "Backend not connected. Check API URL / tunnel.";
    connectionStatus.className = "connection-status error";
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = input.value.trim();
  if (!question) return;
  input.value = "";
  addMessage("user", question);
  const pending = addMessage("assistant pending", "Working live RT BDI reports...");
  try {
    const data = await postJson("/chat", { question, session_id: sessionId });
    pending.remove();
    addMessage("assistant", data.answer, {
      canonical_question: data.canonical_question,
      memory_used: data.memory_used,
      reports_used: data.reports_used,
      date_range: data.date_range,
      rows_used: data.rows_used,
    });
  } catch (error) {
    pending.remove();
    addMessage("assistant error", error.message);
  }
});

document.querySelectorAll("[data-question]").forEach((button) => {
  button.addEventListener("click", () => {
    input.value = button.dataset.question;
    input.focus();
  });
});

document.querySelector("#homeSnapshot").addEventListener("click", async () => {
  addMessage("user", "Home dashboard snapshot");
  const pending = addMessage("assistant pending", "Reading the live Home dashboard...");
  try {
    const response = await fetch(`${apiBase}/home-snapshot`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Home snapshot failed");
    const summary = data.period_summary?.[0] || {};
    pending.remove();
    addMessage("assistant", "Loaded Home dashboard snapshot.", {
      today_snapshot: data.today_snapshot,
      period_summary: summary,
      top_store: data.top_stores?.[0],
      reports_used: ["home_dashboard"],
      rows_used: data.top_stores?.length || 0,
    });
  } catch (error) {
    pending.remove();
    addMessage("assistant error", error.message);
  }
});

checkBackend();
