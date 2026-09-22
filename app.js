// ============================================================
// LUMINA AI - CLIENT APPLICATION ENGINE (APP.JS v2.1)
// Fullscreen Fluid Architecture + Local Multi-Chat History
// GitHub Pages Serverless Mode (Direct Groq) + Backend Fallback
// ============================================================

// ============================================================
// 1. CONFIGURATION & STATE
// ============================================================

let backendUrl = localStorage.getItem("lumina_backend_url") || "http://127.0.0.1:8000/api/v1";
let directGroqKey = localStorage.getItem("lumina_direct_groq_key") || "";

const firebaseConfig = {
    apiKey: "AIzaSyDVAHCFQew6Fgw4B8DRGLDw82ex8sWoT7g",
    authDomain: "aura-plus-cf80f.firebaseapp.com",
    databaseURL: "https://aura-plus-cf80f-default-rtdb.europe-west1.firebasedatabase.app",
    projectId: "aura-plus-cf80f",
    storageBucket: "aura-plus-cf80f.firebasestorage.app",
    messagingSenderId: "739461035408",
    appId: "1:739461035408:web:75052b9f2447b9ed032f15",
    measurementId: "G-NBP1NP00N5"
};

// Global App State
let isFirebaseActive = false;
let auth = null;
let googleProvider = null;
let currentUser = null;
let isGuestMode = true;

let currentAgentMode = "general";
let selectedImageStyle = "photorealistic";
let selectedImageRatio = "1:1";

let voiceEnabled = true;
let isRecording = false;
let recognition = null;
let currentFontScale = 1.0;

// Multi-chat sessions
let sessions = [];
let currentSessionId = null;

// Quota state
let quotaState = { messages_used: 0, messages_max: 250, images_used: 0, images_max: 5 };

// Firebase Init
try {
    if (typeof firebase !== "undefined" && firebase.initializeApp) {
        firebase.initializeApp(firebaseConfig);
        auth = firebase.auth();
        googleProvider = new firebase.auth.GoogleAuthProvider();
        isFirebaseActive = true;
    }
} catch (e) {
    console.info("Firebase bulunamadı, Yerel/Misafir Modu aktif.");
    isFirebaseActive = false;
}

// ============================================================
// 2. INITIALIZATION
// ============================================================

document.addEventListener("DOMContentLoaded", () => {
    initThemeAndFont();
    loadChatSessions();
    setupSpeechRecognition();

    if (isFirebaseActive && auth) {
        auth.onAuthStateChanged((user) => {
            if (user) {
                currentUser = user;
                isGuestMode = false;
                updateUserDisplay(user.displayName || user.email);
                fetchAndDisplayQuota();
            } else {
                currentUser = null;
                isGuestMode = true;
                updateUserDisplay("Misafir Modu");
                fetchAndDisplayQuota();
            }
        });
    } else {
        updateUserDisplay("Misafir Modu");
        fetchAndDisplayQuota();
    }
});

function updateUserDisplay(name) {
    const label = document.getElementById("sidebar-user-name");
    if (label) label.innerText = name;
}

// Fetch quota from backend and update UI
async function fetchAndDisplayQuota() {
    try {
        const token = isFirebaseActive && auth && auth.currentUser ? await auth.currentUser.getIdToken() : "guest_token";
        const res = await fetch(`${backendUrl}/quota`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        if (res.ok) {
            const data = await res.json();
            updateQuotaDisplay(data);
        }
    } catch (e) {
        // Backend offline — keep local default display
        updateQuotaDisplay(quotaState);
    }
}

function updateQuotaDisplay(data) {
    quotaState = { ...quotaState, ...data };
    const bar = document.getElementById("quota-bar");
    if (!bar) return;

    const msgUsed = data.messages_used ?? quotaState.messages_used;
    const msgMax  = data.messages_max  ?? quotaState.messages_max;
    const imgUsed = data.images_used   ?? quotaState.images_used;
    const imgMax  = data.images_max    ?? quotaState.images_max;

    const msgPct = Math.min(100, Math.round((msgUsed / msgMax) * 100));
    const imgPct = Math.min(100, Math.round((imgUsed / imgMax) * 100));

    const msgColor = msgPct >= 90 ? "#ef4444" : msgPct >= 70 ? "#f59e0b" : "#22c55e";
    const imgColor = imgPct >= 80 ? "#ef4444" : "#3b82f6";

    bar.innerHTML = `
        <div style="margin-bottom:5px;">
            <div style="display:flex;justify-content:space-between;font-size:10px;color:var(--text-secondary);margin-bottom:2px;">
                <span>💬 Mesaj</span><span style="color:${msgColor};">${msgUsed}/${msgMax}</span>
            </div>
            <div style="height:4px;background:var(--bg-input);border-radius:4px;overflow:hidden;">
                <div style="height:100%;width:${msgPct}%;background:${msgColor};border-radius:4px;transition:width 0.4s;"></div>
            </div>
        </div>
        <div>
            <div style="display:flex;justify-content:space-between;font-size:10px;color:var(--text-secondary);margin-bottom:2px;">
                <span>🎨 Görsel</span><span style="color:${imgColor};">${imgUsed}/${imgMax}</span>
            </div>
            <div style="height:4px;background:var(--bg-input);border-radius:4px;overflow:hidden;">
                <div style="height:100%;width:${imgPct}%;background:${imgColor};border-radius:4px;transition:width 0.4s;"></div>
            </div>
        </div>
        ${!data.custom_key_active && (msgUsed >= msgMax || imgUsed >= imgMax) ? `
        <div style="margin-top:6px;font-size:10px;color:#ef4444;text-align:center;cursor:pointer;" onclick="openSettingsModal()">
            ⚠️ Kota doldu — API anahtarı ekle
        </div>` : ""}
    `;
}

function showQuotaExceededModal(type = "message") {
    const modal = document.getElementById("quota-exceeded-modal");
    const body  = document.getElementById("quota-exceeded-body");
    if (!modal || !body) return;

    if (type === "image") {
        body.innerHTML = `
            <div style="font-size:36px;margin-bottom:12px;">🎨</div>
            <h3 style="margin-bottom:8px;font-size:17px;">Görsel Kotanız Doldu</h3>
            <p style="color:var(--text-secondary);font-size:13px;line-height:1.6;margin-bottom:14px;">
                Ücretsiz <strong>5 görsel oluşturma</strong> hakkınızı kullandınız.<br>
                Kendi ücretsiz Groq API anahtarınızı ekleyerek sınırsız görsel oluşturabilirsiniz.
            </p>
        `;
    } else {
        body.innerHTML = `
            <div style="font-size:36px;margin-bottom:12px;">💬</div>
            <h3 style="margin-bottom:8px;font-size:17px;">Mesaj Kotanız Doldu</h3>
            <p style="color:var(--text-secondary);font-size:13px;line-height:1.6;margin-bottom:14px;">
                Ücretsiz <strong>250 mesaj</strong> hakkınızı kullandınız.<br>
                Kendi ücretsiz Groq API anahtarınızı ekleyerek sınırsız kullanmaya devam edebilirsiniz.
            </p>
        `;
    }

    modal.style.display = "flex";
}

function closeQuotaExceededModal() {
    const modal = document.getElementById("quota-exceeded-modal");
    if (modal) modal.style.display = "none";
}

function openSettingsFromQuota() {
    closeQuotaExceededModal();
    openSettingsModal();
}


// ============================================================
// 3. THEME & ACCESSIBILITY
// ============================================================

function initThemeAndFont() {
    const savedTheme = localStorage.getItem("lumina_theme") || "dark";
    document.documentElement.setAttribute("data-theme", savedTheme);

    const savedFont = parseFloat(localStorage.getItem("lumina_font_scale") || "1.0");
    currentFontScale = savedFont;
    document.documentElement.style.setProperty("--font-scale", currentFontScale);
}

function cycleTheme() {
    const current = document.documentElement.getAttribute("data-theme") || "dark";
    const themes = ["dark", "midnight", "light"];
    const next = themes[(themes.indexOf(current) + 1) % themes.length];
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("lumina_theme", next);
}

function adjustFontSize(delta) {
    currentFontScale = Math.min(1.35, Math.max(0.85, currentFontScale + delta));
    document.documentElement.style.setProperty("--font-scale", currentFontScale);
    localStorage.setItem("lumina_font_scale", currentFontScale.toFixed(2));
}

// ============================================================
// 4. SIDEBAR & RESPONSIVE DRAWER
// ============================================================

function toggleSidebar() {
    const sidebar = document.getElementById("sidebar");
    const overlay = document.getElementById("sidebar-overlay");
    if (!sidebar) return;

    sidebar.classList.toggle("collapsed");
    if (overlay) {
        overlay.classList.toggle("active", !sidebar.classList.contains("collapsed"));
    }
}

function closeSidebarOnMobile() {
    if (window.innerWidth <= 768) {
        const sidebar = document.getElementById("sidebar");
        const overlay = document.getElementById("sidebar-overlay");
        if (sidebar) sidebar.classList.add("collapsed");
        if (overlay) overlay.classList.remove("active");
    }
}

// ============================================================
// 5. MULTI-CHAT SESSIONS (LOCALSTORAGE)
// ============================================================

function loadChatSessions() {
    try {
        const stored = localStorage.getItem("lumina_chat_sessions");
        sessions = stored ? jsonParseSafe(stored, []) : [];
    } catch (e) {
        sessions = [];
    }

    renderHistoryList();

    if (sessions.length > 0) {
        switchSession(sessions[0].id);
    } else {
        startNewChat();
    }
}

function saveChatSessions() {
    try {
        localStorage.setItem("lumina_chat_sessions", JSON.stringify(sessions));
    } catch (e) {
        console.warn("Sohbet geçmişi kaydedilemedi:", e);
    }
    renderHistoryList();
}

function startNewChat() {
    const newSession = {
        id: "session_" + Date.now(),
        title: "Yeni Sohbet",
        timestamp: Date.now(),
        agentMode: currentAgentMode,
        messages: []
    };
    sessions.unshift(newSession);
    currentSessionId = newSession.id;
    saveChatSessions();
    renderCurrentSession();
    closeSidebarOnMobile();
}

function switchSession(id) {
    currentSessionId = id;
    renderHistoryList();
    renderCurrentSession();
    closeSidebarOnMobile();
}

function deleteSession(e, id) {
    e.stopPropagation();
    sessions = sessions.filter(s => s.id !== id);
    if (currentSessionId === id) {
        if (sessions.length > 0) {
            currentSessionId = sessions[0].id;
        } else {
            startNewChat();
            return;
        }
    }
    saveChatSessions();
    renderCurrentSession();
}

function renderHistoryList() {
    const container = document.getElementById("history-container");
    if (!container) return;

    if (sessions.length === 0) {
        container.innerHTML = `<div style="padding:10px 14px; font-size:12px; color:var(--text-muted);">Henüz geçmiş yok.</div>`;
        return;
    }

    container.innerHTML = sessions.map(s => `
        <div class="history-item ${s.id === currentSessionId ? 'active' : ''}" onclick="switchSession('${s.id}')">
            <span style="overflow:hidden; text-overflow:ellipsis;">💬 ${escapeHTML(s.title)}</span>
            <button class="history-del-btn" onclick="deleteSession(event, '${s.id}')" title="Sil">✕</button>
        </div>
    `).join("");
}

function getCurrentSession() {
    return sessions.find(s => s.id === currentSessionId) || null;
}

function renderCurrentSession() {
    const session = getCurrentSession();
    const chatStream = document.getElementById("chat-stream");
    if (!chatStream) return;

    chatStream.innerHTML = "";

    if (!session || session.messages.length === 0) {
        chatStream.innerHTML = `
            <div class="starter-hero" id="starter-hero">
                <div class="starter-hero-icon">L</div>
                <h2>Lumina AI ile Ne Yapmak İstersin?</h2>
                <p>Duygusal, zeki ve çoklu ajan destekli yapay zeka. Matematik problemlerini adım adım çözer, projelerinizi baştan sona kodlar ve foto-gerçekçi görseller üretir.</p>

                <div class="starter-grid">
                    <div class="starter-chip" onclick="quickAsk('Zor bir matematik problemini adım adım açıkla: 3x^2 - 12x + 9 = 0')">
                        <div class="starter-chip-title">📐 Matematik Çözücü</div>
                        <div class="starter-chip-desc">Denklemleri analiz, formül ve ara sağlamalarla adım adım çözdürün.</div>
                    </div>

                    <div class="starter-chip" onclick="selectAgentMode('software'); quickAsk('/proje React ve FastAPI ile tam donanımlı bir Görev Takip uygulaması mimarisi ve çalışan kodları')">
                        <div class="starter-chip-title">💻 Çoklu Ajan Yazılım</div>
                        <div class="starter-chip-desc">Mimar, Geliştirici ve QA 3'lü ajan ekibiyle baştan sona kodlayın.</div>
                    </div>

                    <div class="starter-chip" onclick="openImageStudioModal()">
                        <div class="starter-chip-title">🎨 Görsel Stüdyosu</div>
                        <div class="starter-chip-desc">AI Prompt Enhancer ile kusursuza yakın fotogerçekçi görseller oluşturun.</div>
                    </div>

                    <div class="starter-chip" onclick="quickAsk('Bugün biraz yoruldum, bir dost gibi dertleşmek istiyorum.')">
                        <div class="starter-chip-title">☕ Samimi Dertleşme</div>
                        <div class="starter-chip-desc">Gerçek bir insan sıcaklığında içini dök, tavsiye ve moral al.</div>
                    </div>
                </div>
            </div>
        `;
        return;
    }

    session.messages.forEach(msg => {
        if (msg.role === "user") {
            renderUserMessageElement(msg.text, false);
        } else if (msg.role === "bot") {
            renderBotMessageElement(msg.text, msg.agentMode, false);
        } else if (msg.role === "image") {
            renderImageCardElement(msg.imageData, false);
        }
    });

    scrollToBottom();
}

// ============================================================
// 6. AGENT MODES
// ============================================================

const AGENT_TITLES = {
    general: "Lumina Genel Asistan",
    software: "🚀 Çoklu Ajan Yazılım Ekibi",
    math: "📐 Matematik & Mantık Ajanı",
    research: "🌐 Canlı Bilgi & Web Ajanı",
    artist: "🎨 Görsel & Sanat Direktörü"
};

function selectAgentMode(mode) {
    currentAgentMode = mode;

    document.querySelectorAll(".agent-nav-item").forEach(item => {
        item.classList.toggle("active", item.getAttribute("data-mode") === mode);
    });

    const badge = document.getElementById("active-agent-title");
    if (badge) badge.innerText = AGENT_TITLES[mode] || "Lumina AI";

    const input = document.getElementById("user-input");
    const placeholders = {
        general: "Lumina'ya sor... (Duygusal ve zeki asistan hazır)",
        software: "Yazılım Ekibine Proje Ver... (Örn: 'React ile Dashboard mimarisi ve kodları')",
        math: "Zor bir matematik veya mantık problemi yazın... (Adım adım çözülecek)",
        research: "Güncel bir konu, haber veya bilgi sorun... (İnternet taranacak)",
        artist: "Görsel veya tasarım fikrinizi anlatın..."
    };
    if (input) {
        input.placeholder = placeholders[mode] || placeholders.general;
        input.focus();
    }
}

function quickAsk(text) {
    const input = document.getElementById("user-input");
    if (input) {
        input.value = text;
        input.focus();
    }
}

// ============================================================
// 7. MESSAGE RENDERING (MARKDOWN, KATEX, HLJS)
// ============================================================

function removeStarterHero() {
    const hero = document.getElementById("starter-hero");
    if (hero) hero.remove();
}

function scrollToBottom() {
    const chatBox = document.getElementById("chat-box");
    if (chatBox) chatBox.scrollTop = chatBox.scrollHeight;
}

function renderUserMessageElement(text, save = true) {
    removeStarterHero();
    const stream = document.getElementById("chat-stream");
    if (!stream) return;

    const row = document.createElement("div");
    row.className = "message-row user-row";
    row.innerHTML = `
        <div class="msg-meta">Siz</div>
        <div class="message-bubble user-bubble">${escapeHTML(text)}</div>
    `;
    stream.appendChild(row);
    scrollToBottom();

    if (save) {
        const session = getCurrentSession();
        if (session) {
            session.messages.push({ role: "user", text: text });
            if (session.messages.length === 1) {
                session.title = text.slice(0, 30) + (text.length > 30 ? "..." : "");
            }
            saveChatSessions();
        }
    }
}

function formatMarkdownAndCode(text) {
    let html = "";
    if (typeof marked !== "undefined") {
        marked.setOptions({ breaks: true, gfm: true });
        html = marked.parse(text);
    } else {
        html = escapeHTML(text).replace(/\n/g, "<br>");
    }

    // Wrap code blocks with header and copy button
    const parser = new DOMParser();
    const doc = parser.parseFromString(`<div>${html}</div>`, "text/html");
    const preBlocks = doc.querySelectorAll("pre");

    preBlocks.forEach((pre) => {
        const code = pre.querySelector("code");
        const lang = (code && code.className) ? code.className.replace("language-", "") : "kod";

        const container = doc.createElement("div");
        container.className = "code-container";
        container.innerHTML = `
            <div class="code-header">
                <span>${lang.toUpperCase()}</span>
                <button class="copy-btn" onclick="copyCode(this)">📋 Kopyala</button>
            </div>
        `;
        pre.parentNode.replaceChild(container, pre);
        container.appendChild(pre);
    });

    return doc.body.firstElementChild.innerHTML;
}

function applyKatexAndHighlight(element) {
    if (typeof hljs !== "undefined") {
        element.querySelectorAll("pre code").forEach((b) => hljs.highlightElement(b));
    }
    if (typeof renderMathInElement !== "undefined") {
        try {
            renderMathInElement(element, {
                delimiters: [
                    { left: "$$", right: "$$", display: true },
                    { left: "$", right: "$", display: false },
                    { left: "\\[", right: "\\]", display: true },
                    { left: "\\(", right: "\\)", display: false }
                ],
                throwOnError: false
            });
        } catch (e) {
            console.debug("KaTeX parse:", e);
        }
    }
}

function copyCode(btn) {
    const container = btn.closest(".code-container");
    const code = container ? (container.querySelector("pre code") || container.querySelector("pre")) : null;
    if (!code) return;

    navigator.clipboard.writeText(code.innerText).then(() => {
        const orig = btn.innerText;
        btn.innerText = "✓ Kopyalandı";
        setTimeout(() => { btn.innerText = orig; }, 2000);
    });
}

function renderBotMessageElement(text, agentMode = "general", save = true) {
    removeStarterHero();
    const stream = document.getElementById("chat-stream");
    if (!stream) return;

    const row = document.createElement("div");
    row.className = "message-row bot-row";

    const title = AGENT_TITLES[agentMode] || "Lumina AI";
    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    row.innerHTML = `
        <div class="msg-meta">
            <strong>${title}</strong> • <span>${timeStr}</span>
        </div>
        <div class="message-bubble bot-bubble">
            ${formatMarkdownAndCode(text)}
        </div>
    `;

    stream.appendChild(row);
    applyKatexAndHighlight(row.querySelector(".bot-bubble"));
    scrollToBottom();

    if (save) {
        const session = getCurrentSession();
        if (session) {
            session.messages.push({ role: "bot", text: text, agentMode: agentMode });
            saveChatSessions();
        }
    }
}

function renderImageCardElement(data, save = true) {
    removeStarterHero();
    const stream = document.getElementById("chat-stream");
    if (!stream) return;

    const row = document.createElement("div");
    row.className = "message-row bot-row";

    const promptText = escapeHTML(data.original_prompt || "Görsel");

    row.innerHTML = `
        <div class="msg-meta">
            <strong>🎨 Lumina Görsel Stüdyosu</strong> • <span>${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
        </div>
        <div class="image-card">
            <img src="${data.image_url}" alt="${promptText}" onclick="openLightbox('${data.image_url}')" title="Büyütmek için tıklayın" loading="lazy">
            <div class="image-card-footer">
                <div style="max-width:65%;">
                    <strong style="font-size:12px;display:block;">${promptText}</strong>
                    <span style="font-size:10px;color:var(--text-secondary);">${data.aspect_ratio} • ${data.style}</span>
                </div>
                <div style="display:flex;gap:6px;">
                    <button class="image-btn" onclick="openLightbox('${data.image_url}')">🔍 Büyüt</button>
                    <a class="image-btn" href="${data.image_url}" target="_blank" download="lumina-image.jpg">⬇️ İndir</a>
                </div>
            </div>
        </div>
    `;

    stream.appendChild(row);
    scrollToBottom();

    if (save) {
        const session = getCurrentSession();
        if (session) {
            session.messages.push({ role: "image", imageData: data });
            saveChatSessions();
        }
    }
}

// ============================================================
// 8. TYPING INDICATOR
// ============================================================

let typingBoxEl = null;

function showTypingIndicator(label = "Lumina düşünüyor...") {
    hideTypingIndicator();
    removeStarterHero();
    const stream = document.getElementById("chat-stream");
    if (!stream) return;

    typingBoxEl = document.createElement("div");
    typingBoxEl.className = "message-row bot-row";
    typingBoxEl.innerHTML = `
        <div class="typing-box">
            <span>${label}</span>
            <div class="typing-dots">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        </div>
    `;
    stream.appendChild(typingBoxEl);
    scrollToBottom();
}

function hideTypingIndicator() {
    if (typingBoxEl && typingBoxEl.parentNode) {
        typingBoxEl.parentNode.removeChild(typingBoxEl);
    }
    typingBoxEl = null;
}

// ============================================================
// 9. CLIENT-SIDE GROQ API DIRECT CALL (GITHUB PAGES MODE)
// ============================================================

async function callDirectGroq(messages, model = "openai/gpt-oss-120b") {
    if (!directGroqKey) {
        throw new Error("Groq API Key yapılandırılmamış.");
    }
    const res = await fetch("https://api.groq.com/openai/v1/chat/completions", {
        method: "POST",
        headers: {
            "Authorization": `Bearer ${directGroqKey}`,
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            model: model,
            messages: messages,
            temperature: 0.65,
            max_tokens: 4096
        })
    });
    if (!res.ok) {
        throw new Error(`Groq API Hatası: ${res.status}`);
    }
    const data = await res.json();
    return data.choices[0].message.content;
}

// ============================================================
// 10. SEND MESSAGE CONTROLLER
// ============================================================

async function sendMessage() {
    const input = document.getElementById("user-input");
    if (!input) return;

    const text = input.value.trim();
    if (!text) return;

    input.value = "";

    // Check for image command
    if (text.startsWith("/görsel") || text.toLowerCase().startsWith("görsel oluştur")) {
        const prompt = text.replace(/^\/görsel|^görsel oluştur/i, "").trim();
        if (prompt) {
            renderUserMessageElement(text);
            await executeImageGeneration(prompt, selectedImageStyle, selectedImageRatio);
            return;
        }
    }

    renderUserMessageElement(text);

    let waitLabel = "Lumina düşünüyor...";
    if (currentAgentMode === "software" || text.startsWith("/proje")) {
        waitLabel = "🚀 Yazılım Ekibi (Mimar → Kodlayıcı → QA) çalışıyor...";
    } else if (currentAgentMode === "math") {
        waitLabel = "📐 Matematik problemi adım adım analiz ediliyor...";
    } else if (currentAgentMode === "research") {
        waitLabel = "🌐 İnternet verileri taranıyor...";
    }

    showTypingIndicator(waitLabel);

    // 1. First Attempt: Backend API
    try {
        const token = isFirebaseActive && auth && auth.currentUser ? await auth.currentUser.getIdToken() : "guest_token";

        const res = await fetch(`${backendUrl}/chat`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({
                message: text,
                agent_mode: currentAgentMode,
                custom_groq_key: directGroqKey || null
            })
        });

        const data = await res.json();
        hideTypingIndicator();

        if (res.ok) {
            renderBotMessageElement(data.reply, data.agent_mode || currentAgentMode);
            speakText(data.reply);
            // Update quota display from response
            if (data.quota) updateQuotaDisplay(data.quota);
            else fetchAndDisplayQuota();
            return;
        } else if (res.status === 403) {
            // Quota exceeded
            showQuotaExceededModal("message");
            return;
        } else {
            renderBotMessageElement(`⚠️ ${data.detail || "Bir hata oluştu."}`, "general");
            return;
        }

    } catch (backendError) {
        console.warn("Backend bağlantısı sağlanamadı, GitHub Pages / Sunucusuz mod kontrol ediliyor...", backendError);

        // 2. Second Attempt: Client-side Direct Groq Mode (for GitHub Pages static host)
        if (directGroqKey) {
            try {
                const sysPrompt = currentAgentMode === "math"
                    ? "Sen üstün matematik ajanısın. Problemleri adım adım çöz, formülleri LaTeX formatında ($) yaz."
                    : "Sen Lumina AI'sın. Empatik, samimi, zeki ve yaşayan bir insan sıcaklığında konuş. Seni kim yaptı diye sorulursa 'LuminaStudios'un kurucusu Arel.' de.";

                const directReply = await callDirectGroq([
                    { role: "system", content: sysPrompt },
                    { role: "user", content: text }
                ]);

                hideTypingIndicator();
                renderBotMessageElement(directReply, currentAgentMode);
                speakText(directReply);
                return;
            } catch (groqErr) {
                hideTypingIndicator();
                renderBotMessageElement(`⚠️ Doğrudan Groq API Hatası: ${groqErr.message}`, "general");
                return;
            }
        }

        // 3. Neither backend nor direct Groq key is available
        hideTypingIndicator();
        renderBotMessageElement(
            "⚠️ **Bağlantı Uyarısı:**\n\n" +
            "Yerel Python backend sunucusuna bağlanılamadı.\n\n" +
            "• **Kendi bilgisayarınızda çalıştırıyorsanız:** `baslat.bat` dosyasını çalıştırarak `python main.py` sunucusunu açın.\n" +
            "• **GitHub Pages üzerinde sunucusuz kullanmak istiyorsanız:** Sol alttaki ⚙️ **Ayarlar** simgesine tıklayıp kendi **Groq API Anahtarınızı** girin.",
            "general"
        );
    }
}

// ============================================================
// 11. IMAGE GENERATION WORKFLOW
// ============================================================

function openImageStudioModal() {
    const modal = document.getElementById("image-modal");
    if (modal) {
        modal.style.display = "flex";
        const input = document.getElementById("image-prompt-input");
        if (input) input.focus();
    }
}

function closeImageStudioModal() {
    const modal = document.getElementById("image-modal");
    if (modal) modal.style.display = "none";
}

function selectImageStyle(style) {
    selectedImageStyle = style;
    document.querySelectorAll("#style-selector .choice-pill").forEach(p => {
        p.classList.toggle("active", p.getAttribute("data-style") === style);
    });
}

function selectImageRatio(ratio) {
    selectedImageRatio = ratio;
    document.querySelectorAll("#ratio-selector .choice-pill").forEach(p => {
        p.classList.toggle("active", p.getAttribute("data-ratio") === ratio);
    });
}

async function submitImageGeneration() {
    const input = document.getElementById("image-prompt-input");
    const prompt = input ? input.value.trim() : "";
    if (!prompt) {
        alert("Lütfen bir görsel açıklaması girin.");
        return;
    }
    closeImageStudioModal();
    input.value = "";
    renderUserMessageElement(`🎨 Görsel İsteği: "${prompt}" [Tarz: ${selectedImageStyle}, Oran: ${selectedImageRatio}]`);
    await executeImageGeneration(prompt, selectedImageStyle, selectedImageRatio);
}

async function executeImageGeneration(prompt, style, ratio) {
    showTypingIndicator("🎨 Prompt zenginleştiriliyor ve ultra gerçekçi görsel oluşturuluyor...");

    // Try backend first
    try {
        const token = isFirebaseActive && auth && auth.currentUser ? await auth.currentUser.getIdToken() : "guest_token";
        const res = await fetch(`${backendUrl}/generate-image`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({
                prompt: prompt,
                style: style,
                aspect_ratio: ratio,
                custom_groq_key: directGroqKey || null
            })
        });
        const data = await res.json();
        hideTypingIndicator();

        if (res.status === 403) {
            showQuotaExceededModal("image");
            return;
        }

        if (res.ok && data.image_url) {
            renderImageCardElement(data);
            speakText("Görseliniz oluşturuldu.");
            if (data.quota) updateQuotaDisplay(data.quota);
            else fetchAndDisplayQuota();
            return;
        }
    } catch (e) {
        console.warn("Backend görsel sunucusu bulunamadı, doğrudan Pollinations motoru kullanılıyor...");
    }

    // Direct Client-Side Pollinations Fallback (Works 100% on GitHub Pages without server!)
    try {
        const dimMap = { "1:1": [1024, 1024], "16:9": [1280, 720], "9:16": [720, 1280] };
        const [w, h] = dimMap[ratio] || [1024, 1024];
        const seed = Math.floor(Math.random() * 900000) + 10000;
        const encoded = encodeURIComponent(`${prompt}, ${style}, 8k, photorealistic, cinematic lighting`);
        const fallbackUrl = `https://image.pollinations.ai/prompt/${encoded}?width=${w}&height=${h}&model=flux-realism&seed=${seed}&nologo=true`;

        hideTypingIndicator();
        renderImageCardElement({
            image_url: fallbackUrl,
            original_prompt: prompt,
            enhanced_prompt: prompt,
            style: style,
            aspect_ratio: ratio
        });
        speakText("Görseliniz oluşturuldu.");
    } catch (err) {
        hideTypingIndicator();
        renderBotMessageElement("⚠️ Görsel oluşturulurken bir hata oluştu.", "artist");
    }
}

// Lightbox
function openLightbox(src) {
    const modal = document.getElementById("lightbox-modal");
    const img = document.getElementById("lightbox-img");
    if (modal && img) {
        img.src = src;
        modal.style.display = "flex";
    }
}

function closeLightbox() {
    const modal = document.getElementById("lightbox-modal");
    if (modal) modal.style.display = "none";
}

// ============================================================
// 12. SETTINGS & AUTH MODALS
// ============================================================

function openSettingsModal() {
    const modal = document.getElementById("settings-modal");
    if (modal) {
        const urlInput = document.getElementById("setting-backend-url");
        const keyInput = document.getElementById("setting-groq-key");
        if (urlInput) urlInput.value = backendUrl;
        if (keyInput) keyInput.value = directGroqKey;
        modal.style.display = "flex";
    }
}

function closeSettingsModal() {
    const modal = document.getElementById("settings-modal");
    if (modal) modal.style.display = "none";
}

function saveSettings() {
    const urlInput = document.getElementById("setting-backend-url");
    const keyInput = document.getElementById("setting-groq-key");

    if (urlInput) {
        backendUrl = urlInput.value.trim() || "http://127.0.0.1:8000/api/v1";
        localStorage.setItem("lumina_backend_url", backendUrl);
    }
    if (keyInput) {
        directGroqKey = keyInput.value.trim();
        localStorage.setItem("lumina_direct_groq_key", directGroqKey);
    }
    closeSettingsModal();
    alert("Ayarlar kaydedildi!");
}

function openAuthModal() {
    const modal = document.getElementById("auth-modal");
    if (modal) modal.style.display = "flex";
}

function closeAuthModal() {
    const modal = document.getElementById("auth-modal");
    if (modal) modal.style.display = "none";
}

function continueAsGuest() {
    isGuestMode = true;
    updateUserDisplay("Misafir Modu");
    closeAuthModal();
}

async function handleEmailLogin() {
    if (!isFirebaseActive) { continueAsGuest(); return; }
    const email = document.getElementById("auth-email").value.trim();
    const pass = document.getElementById("auth-password").value;
    try {
        await auth.signInWithEmailAndPassword(email, pass);
        closeAuthModal();
    } catch (e) {
        alert("Giriş Hatası: " + e.message);
    }
}

async function handleEmailRegister() {
    if (!isFirebaseActive) { continueAsGuest(); return; }
    const email = document.getElementById("auth-email").value.trim();
    const pass = document.getElementById("auth-password").value;
    try {
        await auth.createUserWithEmailAndPassword(email, pass);
        closeAuthModal();
    } catch (e) {
        alert("Kayıt Hatası: " + e.message);
    }
}

async function handleGoogleLogin() {
    if (!isFirebaseActive || !googleProvider) { continueAsGuest(); return; }
    try {
        await auth.signInWithPopup(googleProvider);
        closeAuthModal();
    } catch (e) {
        alert("Google Giriş Hatası: " + e.message);
    }
}

// ============================================================
// 13. SPEECH TO TEXT & TTS
// ============================================================

function setupSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
        recognition = new SpeechRecognition();
        recognition.lang = "tr-TR";
        recognition.continuous = false;
        recognition.interimResults = false;

        recognition.onstart = () => {
            isRecording = true;
            const btn = document.getElementById("mic-btn");
            if (btn) btn.classList.add("active");
        };

        recognition.onresult = (e) => {
            const transcript = e.results[0][0].transcript;
            const input = document.getElementById("user-input");
            if (input) {
                input.value = transcript;
                sendMessage();
            }
        };

        recognition.onerror = () => stopRecording();
        recognition.onend = () => stopRecording();
    }
}

function toggleVoiceInput() {
    if (!recognition) {
        alert("Tarayıcınız ses tanımayı desteklemiyor (Chrome/Edge önerilir).");
        return;
    }
    if (isRecording) {
        recognition.stop();
    } else {
        try { recognition.start(); } catch (e) {}
    }
}

function stopRecording() {
    isRecording = false;
    const btn = document.getElementById("mic-btn");
    if (btn) btn.classList.remove("active");
}

function toggleSpeechOutput() {
    voiceEnabled = !voiceEnabled;
    const btn = document.getElementById("tts-btn");
    if (btn) {
        btn.innerText = voiceEnabled ? "🔊" : "🔇";
    }
    if (!voiceEnabled && "speechSynthesis" in window) {
        window.speechSynthesis.cancel();
    }
}

function speakText(text) {
    if (!voiceEnabled || !("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();

    const clean = text
        .replace(/```[\s\S]*?```/g, "Kod bloğu.")
        .replace(/\$\$[\s\S]*?\$\$/g, "Matematik formülü.")
        .replace(/\$[^$]*\$/g, "")
        .replace(/<[^>]*>/g, "")
        .replace(/[*_#`]/g, "");

    const u = new SpeechSynthesisUtterance(clean);
    u.lang = "tr-TR";
    u.rate = 1.0;
    window.speechSynthesis.speak(u);
}

// ============================================================
// 14. EXPORT & UTILS
// ============================================================

function clearCurrentChat() {
    if (confirm("Bu sohbeti temizlemek istediğinizden emin misiniz?")) {
        const session = getCurrentSession();
        if (session) {
            session.messages = [];
            saveChatSessions();
            renderCurrentSession();
        }
    }
}

function exportChat() {
    const session = getCurrentSession();
    if (!session || session.messages.length === 0) {
        alert("Dışa aktarılacak mesaj yok.");
        return;
    }

    let md = `# Lumina AI — ${session.title}\nTarih: ${new Date(session.timestamp).toLocaleString()}\n\n---\n\n`;
    session.messages.forEach(m => {
        const who = m.role === "user" ? "Kullanıcı" : "Lumina AI";
        const content = m.text || (m.imageData ? `[Görsel: ${m.imageData.original_prompt}](${m.imageData.image_url})` : "");
        md += `### ${who}:\n${content}\n\n`;
    });

    const blob = new Blob([md], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `lumina-chat-${session.id}.md`;
    a.click();
    URL.revokeObjectURL(url);
}

function escapeHTML(str) {
    const p = document.createElement("p");
    p.appendChild(document.createTextNode(str));
    return p.innerHTML;
}

function jsonParseSafe(str, fallback) {
    try { return JSON.parse(str); } catch (e) { return fallback; }
}
