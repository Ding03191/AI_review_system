function resolveApiBase() {
  try {
    const m = document.querySelector('meta[name="api-base"]');
    if (m && m.content) {
      const url = new URL(m.content);
      const host = location.hostname;
      if (host && url.hostname && url.hostname !== host) {
        url.hostname = host;
      }
      return url.origin.replace(/\/+$/, '');
    }
  } catch (e) {}
  const proto = location.protocol === 'https:' ? 'https:' : 'http:';
  const host = location.hostname || '127.0.0.1';
  return `${proto}//${host}:5000`;
}

const ASSIST_API_BASE = resolveApiBase();

(function initChatAssistant() {
  const fab = document.getElementById('chatFab');
  const panel = document.getElementById('chatPanel');
  const closeBtn = document.getElementById('chatClose');
  const form = document.getElementById('chatForm');
  const input = document.getElementById('chatQuestion');
  const micBtn = document.getElementById('chatMic');
  const body = document.getElementById('chatBody');
  if (!fab || !panel || !closeBtn || !form || !input || !body) return;

  function toggle(open) {
    if (open) {
      panel.classList.add('open');
      panel.setAttribute('aria-hidden', 'false');
      input.focus();
    } else {
      panel.classList.remove('open');
      panel.setAttribute('aria-hidden', 'true');
    }
  }

  function appendMessage(role, text) {
    const div = document.createElement('div');
    div.className = `chat-msg ${role}`;
    div.textContent = text;
    body.appendChild(div);
    body.scrollTop = body.scrollHeight;
  }

  fab.addEventListener('click', () => toggle(true));
  closeBtn.addEventListener('click', () => toggle(false));

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recognition = null;
  let listening = false;

  function setListening(next) {
    listening = next;
    if (micBtn) micBtn.classList.toggle('is-listening', listening);
  }

  if (SpeechRecognition && micBtn) {
    recognition = new SpeechRecognition();
    recognition.lang = 'en-US';
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    recognition.onresult = (event) => {
      const text = event.results?.[0]?.[0]?.transcript || '';
      if (text) {
        input.value = text;
        form.requestSubmit();
      }
    };
    recognition.onerror = () => setListening(false);
    recognition.onend = () => setListening(false);

    micBtn.addEventListener('click', () => {
      if (!recognition) return;
      if (listening) {
        recognition.stop();
        setListening(false);
      } else {
        recognition.start();
        setListening(true);
      }
    });
  } else if (micBtn) {
    micBtn.disabled = true;
    micBtn.title = 'Speech input is not supported.';
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const question = input.value.trim();
    if (!question) return;
    appendMessage('user', question);
    input.value = '';
    appendMessage('assistant', 'Thinking...');

    let scope = {};
    if (typeof window.getHistoryFilters === 'function') {
      scope = window.getHistoryFilters() || {};
    }

    try {
      const res = await fetch(`${ASSIST_API_BASE}/api/history/ask`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, scope }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      const answer = data.answer || 'No answer.';
      body.lastChild.textContent = answer;
      if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
        const utter = new SpeechSynthesisUtterance(answer);
        utter.lang = 'en-US';
        utter.rate = 1;
        window.speechSynthesis.speak(utter);
      }
    } catch (err) {
      body.lastChild.textContent = err.message || 'Request failed.';
    }
  });
})();
