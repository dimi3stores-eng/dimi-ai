const chatArea = document.getElementById('chat-area');
const input = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const statusLine = document.getElementById('status-line');
const form = document.getElementById('chat-form');

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
            body: JSON.stringify({ message: text })
        });

        if (!res.ok) throw new Error(`Request failed: ${res.status}`);
        const data = await res.json();
        typingIndicator.remove();
        appendMessage(data.reply || 'No reply received.', 'bot');
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
