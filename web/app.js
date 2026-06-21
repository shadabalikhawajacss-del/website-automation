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

function addMessage(role, content, meta = {}) {
  const article = document.createElement("article");
  article.className = `message ${role}`;
  const body = document.createElement("div");
  body.textContent = content;
  article.appendChild(body);
  if (Object.keys(meta).length) {
    const details = document.createElement("pre");
    details.textContent = JSON.stringify(meta, null, 2);
    article.appendChild(details);
  }
  messages.appendChild(article);
  article.scrollIntoView({ behavior: "smooth", block: "end" });
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

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = input.value.trim();
  if (!question) return;
  input.value = "";
  addMessage("user", question);
  addMessage("assistant pending", "Working live RT BDI reports...");
  const pending = messages.querySelector(".pending:last-child");
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
  try {
    const response = await fetch(`${apiBase}/home-snapshot`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Home snapshot failed");
    const summary = data.period_summary?.[0] || {};
    addMessage("assistant", "Loaded Home dashboard snapshot.", {
      today_snapshot: data.today_snapshot,
      period_summary: summary,
      top_store: data.top_stores?.[0],
    });
  } catch (error) {
    addMessage("assistant error", error.message);
  }
});
