const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const chatFeed = document.getElementById("chat-feed");
const chatStatus = document.getElementById("chat-status");
const tasksList = document.getElementById("tasks-list");
const notesList = document.getElementById("notes-list");
const configList = document.getElementById("config-list");
const healthPill = document.getElementById("health-pill");
const refreshButton = document.getElementById("refresh-button");
const clearChatButton = document.getElementById("clear-chat-button");
const themeToggle = document.getElementById("theme-toggle");
const typingIndicator = document.getElementById("typing-indicator");
const confirmOverlay = document.getElementById("confirm-overlay");
const confirmMessage = document.getElementById("confirm-message");
const confirmOk = document.getElementById("confirm-ok");
const confirmCancel = document.getElementById("confirm-cancel");

// ── Dark / light mode ──────────────────────────────────────────────────────
const savedTheme = localStorage.getItem("theme") || "light";
document.documentElement.setAttribute("data-theme", savedTheme);
themeToggle.textContent = savedTheme === "dark" ? "☀️" : "🌙";

themeToggle.addEventListener("click", () => {
  const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem("theme", next);
  themeToggle.textContent = next === "dark" ? "☀️" : "🌙";
});

// ── Toast notifications ────────────────────────────────────────────────────
function showToast(message, type = "success") {
  const container = document.getElementById("toast-container");
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  requestAnimationFrame(() => toast.classList.add("toast-visible"));
  setTimeout(() => {
    toast.classList.remove("toast-visible");
    toast.addEventListener("transitionend", () => toast.remove());
  }, 3000);
}

// ── Confirm dialog ─────────────────────────────────────────────────────────
function showConfirm(message) {
  return new Promise((resolve) => {
    confirmMessage.textContent = message;
    confirmOverlay.classList.remove("hidden");
    const cleanup = (result) => {
      confirmOverlay.classList.add("hidden");
      confirmOk.removeEventListener("click", onOk);
      confirmCancel.removeEventListener("click", onCancel);
      resolve(result);
    };
    const onOk = () => cleanup(true);
    const onCancel = () => cleanup(false);
    confirmOk.addEventListener("click", onOk);
    confirmCancel.addEventListener("click", onCancel);
  });
}

// ── Helpers ────────────────────────────────────────────────────────────────
function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function truncateText(value, maxLength = 120) {
  const text = String(value || "");
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength - 3) + "...";
}

function formatTime(date) {
  return date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

function dueDateLabel(dueDateStr) {
  if (!dueDateStr) return null;
  const due = new Date(dueDateStr);
  const now = new Date();
  const diffMs = due - now;
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays < 0) return { text: `Overdue by ${Math.abs(diffDays)}d`, cls: "badge-overdue" };
  if (diffDays === 0) return { text: "Due today", cls: "badge-today" };
  if (diffDays === 1) return { text: "Due tomorrow", cls: "badge-soon" };
  if (diffDays <= 3) return { text: `Due in ${diffDays}d`, cls: "badge-soon" };
  return { text: `Due in ${diffDays}d`, cls: "badge-ok" };
}

function statusBadge(status) {
  const map = {
    pending:   { cls: "badge-pending",   label: "Pending" },
    completed: { cls: "badge-completed", label: "Completed" },
    overdue:   { cls: "badge-overdue",   label: "Overdue" },
  };
  const s = map[status] || map.pending;
  return `<span class="status-badge ${s.cls}">${s.label}</span>`;
}

// ── Skeleton loader ────────────────────────────────────────────────────────
function showSkeleton(container, count = 2) {
  container.className = "record-list";
  container.innerHTML = Array(count).fill(`
    <div class="skeleton-card">
      <div class="skeleton-line wide"></div>
      <div class="skeleton-line medium"></div>
      <div class="skeleton-line short"></div>
    </div>
  `).join("");
}

// ── Render tasks ───────────────────────────────────────────────────────────
function renderTasks(tasks) {
  if (!tasks.length) {
    tasksList.className = "record-list empty-state";
    tasksList.innerHTML = `<div class="empty-illustration">📋</div><p>No tasks yet.</p>`;
    return;
  }

  tasksList.className = "record-list";
  tasksList.innerHTML = tasks.map((task) => {
    const due = dueDateLabel(task.due_date);
    const dueBadge = due ? `<span class="status-badge ${due.cls}">${escapeHtml(due.text)}</span>` : "";
    const isCompleted = task.status === "completed";
    return `
      <article class="record-card ${isCompleted ? "card-completed" : ""}" data-id="${task.id}">
        <div class="card-header-row">
          <h3>${escapeHtml(task.title)}</h3>
          <div class="badge-row">
            ${statusBadge(task.status || "pending")}
            ${dueBadge}
          </div>
        </div>
        ${task.description ? `<p class="card-desc">${escapeHtml(task.description)}</p>` : ""}
        <div class="card-actions">
          ${!isCompleted ? `<button class="complete-button" data-action="complete-task" data-id="${task.id}">✓ Complete</button>` : ""}
          <button class="danger-button" data-action="delete-task" data-id="${task.id}">Delete</button>
        </div>
      </article>
    `;
  }).join("");

  tasksList.querySelectorAll("[data-action='complete-task']").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await fetchJson(`/api/v1/tasks/${btn.dataset.id}/complete`, { method: "PATCH" });
      showToast("Task marked as complete ✓");
      await refreshData();
    });
  });

  tasksList.querySelectorAll("[data-action='delete-task']").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const ok = await showConfirm("Delete this task? This cannot be undone.");
      if (!ok) return;
      await fetchJson(`/api/v1/tasks/${btn.dataset.id}`, { method: "DELETE" });
      showToast("Task deleted", "error");
      await refreshData();
    });
  });
}

// ── Render notes ───────────────────────────────────────────────────────────
function renderNotes(notes) {
  if (!notes.length) {
    notesList.className = "record-list empty-state";
    notesList.innerHTML = `<div class="empty-illustration">📝</div><p>No notes yet.</p>`;
    return;
  }

  notesList.className = "record-list";
  notesList.innerHTML = notes.map((note) => {
    const full = escapeHtml(note.content);
    const preview = escapeHtml(truncateText(note.content, 100));
    const isLong = note.content.length > 100;
    const charCount = note.content.length;
    return `
      <article class="record-card" data-id="${note.id}">
        <h3>${escapeHtml(note.title)}</h3>
        <p class="card-desc note-preview" data-full="${full}" data-short="${preview}">
          ${preview}
        </p>
        <div class="note-footer">
          <span class="char-count">${charCount} chars</span>
          ${isLong ? `<button class="expand-button" data-action="expand-note">Show more</button>` : ""}
        </div>
        <div class="card-actions">
          <button class="danger-button" data-action="delete-note" data-id="${note.id}">Delete</button>
        </div>
      </article>
    `;
  }).join("");

  notesList.querySelectorAll("[data-action='expand-note']").forEach((btn) => {
    btn.addEventListener("click", () => {
      const p = btn.closest("article").querySelector(".note-preview");
      const expanded = btn.dataset.expanded === "true";
      p.textContent = expanded ? p.dataset.short : p.dataset.full;
      btn.textContent = expanded ? "Show more" : "Show less";
      btn.dataset.expanded = expanded ? "false" : "true";
    });
  });

  notesList.querySelectorAll("[data-action='delete-note']").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const ok = await showConfirm("Delete this note? This cannot be undone.");
      if (!ok) return;
      await fetchJson(`/api/v1/notes/${btn.dataset.id}`, { method: "DELETE" });
      showToast("Note deleted", "error");
      await refreshData();
    });
  });
}

// ── Render config ──────────────────────────────────────────────────────────
function renderConfig(config, healthOk) {
  healthPill.textContent = healthOk ? "Healthy" : "Needs attention";
  healthPill.className = `pill ${healthOk ? "ok" : "warn"}`;
  const mcpLines = (config.mcp_servers || []).map((server) => {
    const base = `${server.name} (${server.transport})`;
    if (server.reachable) {
      const tools = server.tools || [];
      const toolsPreview = tools.length > 3 ? `${tools.slice(0, 3).join(", ")}, +${tools.length - 3} more` : (tools.join(", ") || "none");
      return `<li>MCP: ${escapeHtml(base)} - ${server.tool_count} tool(s): ${escapeHtml(truncateText(toolsPreview, 90))}</li>`;
    }
    return `<li>MCP: ${escapeHtml(base)} - unreachable</li>`;
  }).join("");

  configList.innerHTML = `
    <li>Vertex AI: ${config.vertex_ai_enabled ? "enabled" : "disabled"}</li>
    <li>Project configured: ${config.google_cloud_project_configured ? "yes" : "no"}</li>
    <li>Location: ${escapeHtml(config.google_cloud_location)}</li>
    <li>Model: ${escapeHtml(config.model)}</li>
    <li>Developer API key set: ${config.developer_api_key_configured ? "yes" : "no"}</li>
    <li>Google Calendar configured: ${config.google_calendar_configured ? "yes" : "no"}</li>
    <li>MCP servers configured: ${config.mcp_servers_configured || 0}</li>
    ${mcpLines}
  `;
}

// ── Chat helpers ───────────────────────────────────────────────────────────
function appendMessage(role, content, extraHtml = "") {
  const article = document.createElement("article");
  article.className = `message ${role}`;
  article.innerHTML = `
    <div class="message-role">${role === "user" ? "You" : role === "error" ? "System" : "Assistant"}</div>
    <p>${escapeHtml(content)}</p>
    ${extraHtml}
    <div class="message-time">${formatTime(new Date())}</div>
  `;
  chatFeed.appendChild(article);
  chatFeed.scrollTop = chatFeed.scrollHeight;
}

function planMarkup(plan, toolResults) {
  const tools = (toolResults || []).map((item) =>
    `<li>${escapeHtml(item.tool_name)}</li>`
  ).join("");
  return `<ul class="tool-list">${tools || "<li>No tools executed.</li>"}</ul>`;
}

function showTyping() {
  typingIndicator.classList.remove("hidden");
  chatFeed.scrollTop = chatFeed.scrollHeight;
}

function hideTyping() {
  typingIndicator.classList.add("hidden");
}

// ── Fetch helper ───────────────────────────────────────────────────────────
async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const detail = typeof body === "object" && body?.detail ? body.detail : body;
    throw new Error(detail || `Request failed with status ${response.status}`);
  }
  return body;
}

// ── Refresh data ───────────────────────────────────────────────────────────
async function refreshData() {
  showSkeleton(tasksList);
  showSkeleton(notesList);
  const [health, config, tasks, notes] = await Promise.all([
    fetchJson("/health"),
    fetchJson("/api/v1/config"),
    fetchJson("/api/v1/tasks"),
    fetchJson("/api/v1/notes"),
  ]);
  renderConfig(config, health.status === "ok");
  renderTasks(tasks);
  renderNotes(notes);
}

// ── Chat submit ────────────────────────────────────────────────────────────
chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = chatInput.value.trim();
  if (!message) return;

  appendMessage("user", message);
  chatStatus.textContent = "Running workflow...";
  chatInput.value = "";
  showTyping();

  try {
    const result = await fetchJson("/api/v1/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    hideTyping();
    appendMessage("assistant", result.answer, planMarkup(result.plan, result.tool_results));
    chatStatus.textContent = "Workflow completed";
    showToast("Workflow completed ✓");
    await refreshData();
  } catch (error) {
    hideTyping();
    appendMessage("error", error.message);
    chatStatus.textContent = "Action needed";
    showToast(error.message, "error");
  }
});

// ── Prompt chips ───────────────────────────────────────────────────────────
document.querySelectorAll(".prompt-chip").forEach((button) => {
  button.addEventListener("click", () => {
    chatInput.value = button.dataset.prompt || "";
    chatInput.focus();
  });
});

// ── Refresh button ─────────────────────────────────────────────────────────
refreshButton.addEventListener("click", async () => {
  chatStatus.textContent = "Refreshing data...";
  try {
    await refreshData();
    chatStatus.textContent = "Data refreshed";
    showToast("Data refreshed ✓");
  } catch (error) {
    appendMessage("error", error.message);
    chatStatus.textContent = "Refresh failed";
    showToast(error.message, "error");
  }
});

// ── Clear chat ─────────────────────────────────────────────────────────────
clearChatButton.addEventListener("click", () => {
  chatFeed.innerHTML = `
    <article class="message assistant">
      <div class="message-role">Assistant</div>
      <p>Ask me to create tasks, capture notes, or summarize your schedule.</p>
      <div class="message-time">${formatTime(new Date())}</div>
    </article>
  `;
  chatStatus.textContent = "Ready";
  showToast("Chat cleared");
});

// ── Startup ────────────────────────────────────────────────────────────────
refreshData().catch((error) => {
  appendMessage("error", error.message);
  chatStatus.textContent = "Startup check failed";
  showToast(error.message, "error");
});
