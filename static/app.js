const chatArea = document.getElementById('chat-area');
const input = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const statusLine = document.getElementById('status-line');
const form = document.getElementById('chat-form');
const modelSelect = document.getElementById('model-select');

const SESSION_KEY = 'dimi-session-id';
let sessionId = localStorage.getItem(SESSION_KEY);
if (!sessionId) {
    sessionId = crypto.randomUUID();
    localStorage.setItem(SESSION_KEY, sessionId);
}

function appendMessage(text, sender = 'bot') {
    const row = document.createElement('div');
    row.className = `message-row ${sender}`;

    const avatar = document.createElement('div');
    avatar.className = 'avatar';
    avatar.textContent = sender === 'user' ? 'You' : 'AI';

    const bubble = document.createElement('div');
    bubble.className = 'msg';
    bubble.textContent = text;

    if (sender === 'user') {
        row.appendChild(bubble);
        row.appendChild(avatar);
    } else {
        row.appendChild(avatar);
        row.appendChild(bubble);
    }

    chatArea.appendChild(row);
    chatArea.scrollTop = chatArea.scrollHeight;
    return bubble;
}

function setStatus(text, state = 'ok') {
    statusLine.dataset.state = state;
    statusLine.replaceChildren();

    const dot = document.createElement('span');
    dot.className = 'status-dot';

    statusLine.appendChild(dot);
    statusLine.appendChild(document.createTextNode(text));
}

function showTyping() {
    const indicator = document.createElement('div');
    indicator.className = 'message-row bot typing';
    indicator.innerHTML = `
        <div class="avatar">AI</div>
        <div class="msg system-hint">typing...</div>
    `;
    chatArea.appendChild(indicator);
    chatArea.scrollTop = chatArea.scrollHeight;
    return indicator;
}

function buildFeedbackControls(turnId, bubble) {
    if (!turnId) return;
    const bar = document.createElement('div');
    bar.className = 'feedback-bar';

    const label = document.createElement('span');
    label.textContent = 'Rate this response:';
    bar.appendChild(label);

    const addBtn = (emoji, rating) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.textContent = emoji;
        btn.addEventListener('click', async () => {
            const comment = prompt('Optional feedback comment?') || '';
            try {
                await fetch('/feedback', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        turn_id: turnId,
                        session: sessionId,
                        rating,
                        comment,
                    }),
                });
                bar.querySelectorAll('button').forEach((b) => (b.disabled = true));
                label.textContent = 'Thanks for your feedback!';
            } catch (err) {
                console.error('Feedback failed', err);
                label.textContent = 'Feedback failed — try again later';
            }
        });
        bar.appendChild(btn);
    };

    addBtn('👍', 'good');
    addBtn('👎', 'bad');
    bubble.appendChild(bar);
}

async function streamReply(res, turnId) {
    const decoder = new TextDecoder();
    const reader = res.body.getReader();
    const bubble = appendMessage('', 'bot');
    let text = '';

    while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        text += decoder.decode(value, { stream: true });
        bubble.textContent = text;
        chatArea.scrollTop = chatArea.scrollHeight;
    }

    text += decoder.decode();
    bubble.textContent = text || 'No reply received.';
    buildFeedbackControls(turnId, bubble);
    chatArea.scrollTop = chatArea.scrollHeight;
}

async function sendMessage() {
    const text = input.value.trim();
    if (!text) return;

    appendMessage(text, 'user');
    input.value = '';
    input.disabled = true;
    sendBtn.disabled = true;
    chatArea.setAttribute('aria-busy', 'true');
    setStatus('Sending to local model...', 'warn');

    const typingIndicator = showTyping();
    try {
        const res = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: text,
                model: modelSelect?.value || undefined,
                session: sessionId,
            }),
        });

        if (!res.ok || !res.body) throw new Error(`Request failed: ${res.status}`);
        typingIndicator.remove();
        const turnId = res.headers.get('x-turn-id');
        await streamReply(res, turnId);
        setStatus('Connected to local workspace', 'ok');
    } catch (err) {
        typingIndicator.remove();
        appendMessage('There was a problem reaching your local model.', 'bot');
        setStatus('Disconnected - check your local model runtime', 'error');
        console.error(err);
    } finally {
        input.disabled = false;
        sendBtn.disabled = false;
        input.focus();
        chatArea.removeAttribute('aria-busy');
    }
}

form.addEventListener('submit', (e) => {
    e.preventDefault();
    sendMessage();
});

appendMessage("Hi, I'm your Windows-style Dimi3 twin. Ask me anything about business, coding, or music!", 'bot');
input.focus();
