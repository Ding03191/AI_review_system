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
  return "";
}

const LAYOUT_API_BASE = resolveApiBase();

function getStoredUser() {
  try {
    return JSON.parse(localStorage.getItem('user') || '{}');
  } catch (e) {
    return {};
  }
}

function updateUserRail() {
  const user = getStoredUser();
  const studentId = user.studentId || localStorage.getItem('studentId') || '';
  const role = user.role || '';
  const isTeacher = role && role !== 'applicant';

  document.querySelectorAll('[data-user-name]').forEach((el) => {
    el.textContent = isTeacher ? 'Teacher' : `Student ID: ${studentId || '--'}`;
  });
  document.querySelectorAll('[data-user-student]').forEach((el) => {
    if (isTeacher) {
      el.textContent = '';
      el.classList.add('is-hidden');
    } else {
      el.classList.remove('is-hidden');
      el.textContent = `Student ID: ${studentId || '--'}`;
    }
  });
  document.querySelectorAll('[data-user-initial]').forEach((el) => {
    const initial = (studentId || 'U').trim().slice(0, 1);
    el.textContent = initial || 'U';
  });

  document.querySelectorAll('[data-role="teacher"]').forEach((el) => {
    el.classList.toggle('is-hidden', !isTeacher);
  });
}

window.updateUserRail = updateUserRail;

function isAuthPage() {
  return /login\.html|register\.html/i.test(location.pathname || '');
}

async function syncUserSession() {
  try {
    const res = await fetch(`${LAYOUT_API_BASE}/api/auth/me`, { credentials: 'include' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (data?.ok && data?.data?.user) {
      localStorage.setItem('user', JSON.stringify(data.data.user));
      if (data.data.user?.studentId) localStorage.setItem('studentId', data.data.user.studentId);
      return data.data.user;
    }
  } catch (e) {}
  localStorage.removeItem('user');
  localStorage.removeItem('studentId');
  if (!isAuthPage()) {
    location.href = 'login.html';
  }
  return null;
}

function bindUserMenu() {
  const btn = document.getElementById('userMenuBtn');
  const gear = document.getElementById('userMenuGear');
  const panel = document.getElementById('userMenuPanel');
  const logoutBtn = document.getElementById('btnLogout');
  if (!btn || !panel) return;

  function closeMenu() {
    panel.classList.remove('open');
    panel.setAttribute('aria-hidden', 'true');
    btn.setAttribute('aria-expanded', 'false');
  }
  function openMenu() {
    panel.classList.add('open');
    panel.setAttribute('aria-hidden', 'false');
    btn.setAttribute('aria-expanded', 'true');
  }

  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    if (panel.classList.contains('open')) {
      closeMenu();
    } else {
      openMenu();
    }
  });
  if (gear) {
    gear.addEventListener('click', (e) => {
      e.stopPropagation();
      if (panel.classList.contains('open')) {
        closeMenu();
      } else {
        openMenu();
      }
    });
  }

  document.addEventListener('click', (e) => {
    if (!panel.contains(e.target) && !btn.contains(e.target)) closeMenu();
  });

  if (logoutBtn) {
    logoutBtn.addEventListener('click', async () => {
      try {
        await fetch(`${LAYOUT_API_BASE}/api/auth/logout`, {
          method: 'POST',
          credentials: 'include',
        });
      } catch (e) {}
      localStorage.removeItem('user');
      localStorage.removeItem('userName');
      localStorage.removeItem('studentId');
      location.href = 'login.html';
    });
  }
}

async function initLayout() {
  await syncUserSession();
  updateUserRail();
  bindUserMenu();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    initLayout();
  });
} else {
  initLayout();
}
