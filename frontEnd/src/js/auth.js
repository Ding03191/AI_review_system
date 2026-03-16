// auth.js: login/register only
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

const API_BASE = resolveApiBase();

async function apiLogin(studentId, password) {
  let res;
  try {
    res = await fetch(`${API_BASE}/api/auth/login`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ studentId, password }),
    });
  } catch (err) {
    throw new Error('無法連線到後端服務，請確認後端已啟動');
  }
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || 'Login failed');
  try {
    localStorage.setItem('user', JSON.stringify(data.data.user || {}));
    if (data.data.user?.studentId) localStorage.setItem('studentId', data.data.user.studentId);
  } catch (e) {}
  return data.data.user;
}

async function apiRegister(name, studentId, password) {
  const res = await fetch(`${API_BASE}/api/auth/register`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, studentId, password }),
  });
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || 'Register failed');
  return data.data || {};
}

function bindPasswordToggles() {
  document.querySelectorAll('.icon-btn[data-toggle]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const t = document.querySelector(btn.dataset.toggle);
      if (t) t.type = t.type === 'password' ? 'text' : 'password';
    });
  });
}

function initLogin() {
  const loginForm = document.getElementById('formLogin');
  if (!loginForm) return;
  const err = document.getElementById('loginError');
  loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(loginForm);
    const studentId = fd.get('studentId');
    const pwd = fd.get('password');
    const btn = loginForm.querySelector('button[type="submit"]');
    err.textContent = '';
    btn.disabled = true;
    btn.dataset.loading = 'true';
    try {
      await apiLogin(studentId, pwd);
      location.href = 'review.html';
    } catch (ex) {
      err.textContent = ex.message || 'Login failed';
    } finally {
      btn.disabled = false;
      btn.dataset.loading = '';
    }
  });
}

function initRegister() {
  const registerForm = document.getElementById('formRegister');
  if (!registerForm) return;
  const err = document.getElementById('registerError');
  registerForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(registerForm);
    const name = fd.get('name')?.toString().trim();
    const studentId = fd.get('studentId')?.toString().trim();
    const pwd = fd.get('password')?.toString();
    const btn = registerForm.querySelector('button[type="submit"]');
    err.textContent = '';
    btn.disabled = true;
    btn.dataset.loading = 'true';
    try {
      if (!studentId) throw new Error('Student ID required');
      if ((pwd || '').length < 6) throw new Error('Password must be 6+ chars');
      await apiRegister(name, studentId, pwd);
      location.href = 'login.html';
    } catch (ex) {
      err.textContent = ex.message || 'Register failed';
    } finally {
      btn.disabled = false;
      btn.dataset.loading = '';
    }
  });
}

function initGoogleLogin() {
  const btn = document.getElementById('btnGoogleLogin');
  if (!btn) return;
  btn.addEventListener('click', () => {
    window.location.href = `${API_BASE}/api/auth/google/login`;
  });
}

bindPasswordToggles();
initLogin();
initRegister();
initGoogleLogin();
