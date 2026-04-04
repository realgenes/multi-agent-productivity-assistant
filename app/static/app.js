const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const chatFeed = document.getElementById("chat-feed");
const chatStatus = document.getElementById("chat-status");
const tasksList = document.getElementById("tasks-list");
const notesList = document.getElementById("notes-list");
const configList = document.getElementById("config-list");
const healthPill = document.getElementById("health-pill");
const refreshButton = document.getElementById("refresh-button");

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

function appendMessage(role, content, extraHtml = "") {
  const article = document.createElement("article");
  article.className = `message ${role}`;
  article.innerHTML = `
    <div class="message-role">${role === "user" ? "You" : role === "error" ? "System" : "Assistant"}</div>
    <p>${escapeHtml(content)}</p>
    ${extraHtml}
  `;
  chatFeed.appendChild(article);
  chatFeed.scrollTop = chatFeed.scrollHeight;
}

function renderTasks(tasks) {
  if (!tasks.length) {
    tasksList.className = "record-list empty-state";
    tasksList.textContent = "No tasks yet.";
    return;
  }

  tasksList.className = "record-list";
  tasksList.innerHTML = tasks.map((task) => `
    <article class="record-card">
      <h3>${escapeHtml(task.title)}</h3>
      <div class="meta">Status: ${escapeHtml(task.status)}</div>
      <div class="meta">Due: ${escapeHtml(task.due_date || "Not set")}</div>
      <p>${escapeHtml(task.description || "No description provided.")}</p>
    </article>
  `).join("");
}

function renderNotes(notes) {
  if (!notes.length) {
    notesList.className = "record-list empty-state";
    notesList.textContent = "No notes yet.";
    return;
  }

  notesList.className = "record-list";
  notesList.innerHTML = notes.map((note) => `
    <article class="record-card">
      <h3>${escapeHtml(note.title)}</h3>
      <p>${escapeHtml(note.content)}</p>
    </article>
  `).join("");
}

function renderConfig(config, healthOk) {
  healthPill.textContent = healthOk ? "Healthy" : "Needs attention";
  healthPill.className = `pill ${healthOk ? "ok" : "warn"}`;
  const mcpLines = (config.mcp_servers || []).map((server) => {
    const base = `${server.name} (${server.transport})`;
    if (server.reachable) {
      const tools = server.tools || [];
      const toolsPreview = tools.length > 3 ? `${tools.slice(0, 3).join(", ")}, +${tools.length - 3} more` : (tools.join(", ") || "none");
      return `<li title="${escapeHtml(`${base} - ${tools.join(", ") || "none"}`)}">MCP: ${escapeHtml(base)} - ${server.tool_count} tool(s): ${escapeHtml(truncateText(toolsPreview, 90))}</li>`;
    }
    const errorText = server.error ? truncateText(server.error, 120) : "";
    return `<li title="${escapeHtml(server.error || "")}">MCP: ${escapeHtml(base)} - unreachable${errorText ? `: ${escapeHtml(errorText)}` : ""}</li>`;
  }).join("");

  configList.innerHTML = `
    <li>Vertex AI: ${config.vertex_ai_enabled ? "enabled" : "disabled"}</li>
    <li>Project configured: ${config.google_cloud_project_configured ? "yes" : "no"}</li>
    <li>Location: ${escapeHtml(config.google_cloud_location)}</li>
    <li>Model: ${escapeHtml(config.model)}</li>
    <li>Developer API key set: ${config.developer_api_key_configured ? "yes" : "no"}</li>
    <li>MCP servers configured: ${config.mcp_servers_configured || 0}</li>
    ${mcpLines}
  `;
}

function planMarkup(plan, toolResults) {
  const steps = (plan?.steps || []).map((step) =>
    `<li><strong>${escapeHtml(step.agent)}</strong>: ${escapeHtml(step.action)}</li>`
  ).join("");

  const tools = (toolResults || []).map((item) =>
    `<li>${escapeHtml(item.tool_name)}</li>`
  ).join("");

  return `
    <ul class="plan-list">${steps || "<li>No plan steps returned.</li>"}</ul>
    <ul class="tool-list">${tools || "<li>No tools executed.</li>"}</ul>
  `;
}

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

async function refreshData() {
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

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = chatInput.value.trim();
  if (!message) return;

  appendMessage("user", message);
  chatStatus.textContent = "Running workflow...";
  chatInput.value = "";

  try {
    const result = await fetchJson("/api/v1/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });

    appendMessage("assistant", result.answer, planMarkup(result.plan, result.tool_results));
    chatStatus.textContent = "Workflow completed";
    await refreshData();
  } catch (error) {
    appendMessage("error", error.message);
    chatStatus.textContent = "Action needed";
  }
});

document.querySelectorAll(".prompt-chip").forEach((button) => {
  button.addEventListener("click", () => {
    chatInput.value = button.dataset.prompt || "";
    chatInput.focus();
  });
});

refreshButton.addEventListener("click", async () => {
  chatStatus.textContent = "Refreshing data...";
  try {
    await refreshData();
    chatStatus.textContent = "Data refreshed";
  } catch (error) {
    appendMessage("error", error.message);
    chatStatus.textContent = "Refresh failed";
  }
});

refreshData().catch((error) => {
  appendMessage("error", error.message);
  chatStatus.textContent = "Startup check failed";
});

