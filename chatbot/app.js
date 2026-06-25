/* =========================================================================
 *  Custom n8n Chatbot UI
 *  세련된 커스텀 챗봇 화면을 n8n "Chat Trigger" webhook 에 연결합니다.
 * ========================================================================= */

const CONFIG = {
  // 👉 n8n Chat Trigger 의 production webhook URL
  webhookUrl:
    "https://mj7531.app.n8n.cloud/webhook/d77d6db7-532a-4309-9495-23cc90ee5c1b/chat",
  // 첫 화면 인사말 (빈 문자열이면 표시 안 함)
  welcomeMessage: "안녕하세요! 무엇을 도와드릴까요? 😊",
  botName: "Assistant",
};

// 테스트용: ?webhook=<URL> 쿼리 파라미터로 임시 교체 가능
const _params = new URLSearchParams(location.search);
if (_params.get("webhook")) CONFIG.webhookUrl = _params.get("webhook");

// localStorage 가 막힌 환경(file:// 로 직접 열기 등)에서도 동작하도록 안전 래퍼
const _mem = {};
const store = {
  get(k) {
    try {
      return localStorage.getItem(k);
    } catch {
      return k in _mem ? _mem[k] : null;
    }
  },
  set(k, v) {
    try {
      localStorage.setItem(k, v);
    } catch {
      _mem[k] = v;
    }
  },
  remove(k) {
    try {
      localStorage.removeItem(k);
    } catch {
      delete _mem[k];
    }
  },
};

const state = {
  sessionId: getOrCreateSessionId(),
  sending: false,
};

const els = {
  messages: document.getElementById("messages"),
  form: document.getElementById("chat-form"),
  input: document.getElementById("input"),
  send: document.getElementById("send-btn"),
  status: document.getElementById("status"),
  reset: document.getElementById("reset-btn"),
  themeToggle: document.getElementById("theme-toggle"),
};

/* ---------- session ---------- */
function getOrCreateSessionId() {
  let id = store.get("n8n-chat-session");
  if (!id) {
    id =
      (crypto.randomUUID && crypto.randomUUID()) ||
      "sess-" + Math.random().toString(36).slice(2) + Date.now().toString(36);
    store.set("n8n-chat-session", id);
  }
  return id;
}

/* ---------- theme ---------- */
function toggleTheme() {
  const cur = document.documentElement.getAttribute("data-theme");
  const next = cur === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  store.set("n8n-chat-theme", next);
}

/* ---------- rendering ---------- */
function renderMarkdown(text) {
  if (window.marked && window.DOMPurify) {
    const html = window.marked.parse(String(text), { breaks: true });
    return window.DOMPurify.sanitize(html);
  }
  const div = document.createElement("div");
  div.textContent = String(text);
  return div.innerHTML.replace(/\n/g, "<br>");
}

/* ---------- download buttons ---------- */
const FILE_RE = /\.(pdf|docx?|xlsx?|pptx?|hwpx?|zip|csv|txt|rtf|jpe?g|png)(\?|#|$)/i;
const GD_VIEW_RE = /drive\.google\.com\/file\/d\/([^/?#]+)/i;
const FILE_ICON =
  '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>';
const DL_ICON =
  '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12M7 10l5 5 5-5M5 21h14"/></svg>';

function looksDownloadable(href) {
  return (
    FILE_RE.test(href) ||
    /[?&]export=download/i.test(href) ||
    /[?&]download(=|&|$)/i.test(href) ||
    /#download$/i.test(href)
  );
}

// 봇 답변 속 파일/구글드라이브 링크를 다운로드 버튼 카드로 변환
function decorateDownloads(container) {
  container.querySelectorAll("a").forEach((a) => {
    let href = a.getAttribute("href") || "";
    const text = (a.textContent || "").trim();
    const gd = href.match(GD_VIEW_RE);
    if (gd) href = "https://drive.google.com/uc?export=download&id=" + gd[1];
    if (!gd && !looksDownloadable(href)) return;

    let name = text;
    if (!name || /^https?:/i.test(name)) {
      try {
        name = decodeURIComponent(href.split(/[?#]/)[0].split("/").pop()) || "첨부 파일";
      } catch {
        name = "첨부 파일";
      }
    }

    const card = document.createElement("a");
    card.className = "dl-card";
    card.href = href;
    card.target = "_blank";
    card.rel = "noopener noreferrer";
    card.setAttribute("download", "");
    card.innerHTML =
      '<span class="dl-card__icon">' + FILE_ICON + "</span>" +
      '<span class="dl-card__body"><span class="dl-card__name"></span>' +
      '<span class="dl-card__hint">클릭하면 다운로드</span></span>' +
      '<span class="dl-card__arrow">' + DL_ICON + "</span>";
    card.querySelector(".dl-card__name").textContent = name;
    a.replaceWith(card);
  });
}

function addMessage(text, who) {
  const row = document.createElement("div");
  row.className = `msg msg--${who}`;
  const bubble = document.createElement("div");
  bubble.className = "msg__bubble";
  if (who === "bot") {
    bubble.innerHTML = renderMarkdown(text);
    decorateDownloads(bubble);
  } else {
    bubble.textContent = text;
  }
  row.appendChild(bubble);
  els.messages.appendChild(row);
  scrollToBottom();
  return row;
}

function showTyping() {
  const row = document.createElement("div");
  row.className = "msg msg--bot";
  row.id = "typing";
  row.innerHTML =
    '<div class="msg__bubble msg__bubble--typing"><span></span><span></span><span></span></div>';
  els.messages.appendChild(row);
  scrollToBottom();
}
function hideTyping() {
  const t = document.getElementById("typing");
  if (t) t.remove();
}

function scrollToBottom() {
  els.messages.scrollTo({ top: els.messages.scrollHeight, behavior: "smooth" });
}

/* ---------- network ---------- */
async function sendToN8n(message) {
  const res = await fetch(CONFIG.webhookUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      action: "sendMessage",
      sessionId: state.sessionId,
      chatInput: message,
    }),
  });
  if (!res.ok) throw new Error(`서버 응답 오류 (HTTP ${res.status})`);
  const raw = await res.text();
  let data;
  try {
    data = JSON.parse(raw);
  } catch {
    return raw || "(빈 응답)";
  }
  return extractReply(data);
}

// n8n 워크플로우 마지막 노드 구성에 따라 응답 형태가 다양해서 폭넓게 처리
function extractReply(data) {
  if (data == null) return "(빈 응답)";
  if (typeof data === "string") return data;
  if (Array.isArray(data)) {
    return data.map(extractReply).filter(Boolean).join("\n\n");
  }
  if (typeof data === "object") {
    return (
      data.output ??
      data.text ??
      data.response ??
      data.message ??
      data.answer ??
      data.reply ??
      JSON.stringify(data, null, 2)
    );
  }
  return String(data);
}

/* ---------- flow ---------- */
async function handleSubmit(e) {
  e.preventDefault();
  const text = els.input.value.trim();
  if (!text || state.sending) return;

  addMessage(text, "user");
  els.input.value = "";
  autoResize();
  setSending(true);
  showTyping();

  try {
    const reply = await sendToN8n(text);
    hideTyping();
    addMessage(reply, "bot");
  } catch (err) {
    hideTyping();
    addMessage(
      `⚠️ 메시지를 보내지 못했어요.\n\n**${err.message}**\n\n` +
        "확인해 주세요:\n" +
        "- n8n 워크플로우가 **Active** 상태인지\n" +
        "- Chat Trigger 의 **Allowed Origins (CORS)** 에 이 사이트 주소가 등록됐는지\n" +
        "- `app.js` 의 `webhookUrl` 이 맞는지",
      "bot"
    );
  } finally {
    setSending(false);
    els.input.focus();
  }
}

function setSending(v) {
  state.sending = v;
  els.send.disabled = v;
  els.status.textContent = v ? "입력 중…" : "온라인";
}

function autoResize() {
  els.input.style.height = "auto";
  els.input.style.height = Math.min(els.input.scrollHeight, 140) + "px";
}

function resetConversation() {
  els.messages.innerHTML = "";
  store.remove("n8n-chat-session");
  state.sessionId = getOrCreateSessionId();
  if (CONFIG.welcomeMessage) addMessage(CONFIG.welcomeMessage, "bot");
}

/* ---------- init ---------- */
function init() {
  document.querySelector(".chat-header__title").textContent = CONFIG.botName;
  document.title = CONFIG.botName;

  els.form.addEventListener("submit", handleSubmit);
  els.input.addEventListener("input", autoResize);
  els.input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      els.form.requestSubmit();
    }
  });
  els.reset.addEventListener("click", resetConversation);
  els.themeToggle.addEventListener("click", toggleTheme);

  if (CONFIG.welcomeMessage) addMessage(CONFIG.welcomeMessage, "bot");
  els.input.focus();
}

document.addEventListener("DOMContentLoaded", init);
