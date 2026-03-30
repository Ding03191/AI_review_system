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

function getSurname(name) {
  const text = String(name || '').trim();
  if (!text) return '';
  return text.slice(0, 1);
}

function updateUserRail() {
  const user = getStoredUser();
  const studentId = user.studentId || localStorage.getItem('studentId') || '';
  const displayName = (user.name || user.studentName || '').toString().trim();
  const surname = getSurname(displayName) || (studentId || 'U').trim().slice(0, 1) || 'U';

  document.querySelectorAll('[data-user-name]').forEach((el) => {
    el.textContent = `姓名: ${displayName || '--'}`;
  });
  document.querySelectorAll('[data-user-student]').forEach((el) => {
    el.textContent = `學號: ${studentId || '--'}`;
  });
  document.querySelectorAll('[data-user-initial]').forEach((el) => {
    el.textContent = surname;
    el.style.visibility = 'visible';
  });

  const role = (user.role || '').trim();
  const isTeacher = !!role && role !== 'applicant';
  document.querySelectorAll('[data-role="teacher"]').forEach((el) => {
    if (isTeacher) {
      el.classList.remove('is-hidden');
      el.style.display = '';
    } else {
      el.classList.add('is-hidden');
      el.style.display = 'none';
    }
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
  localStorage.removeItem('userName');
  localStorage.removeItem('studentId');
  if (!isAuthPage()) {
    location.href = 'login.html';
  }
  return null;
}

function bindUserMenu() {
  const gear = document.getElementById('userMenuGear');
  const panel = document.getElementById('userMenuPanel');
  const logoutBtn = document.getElementById('btnLogout');
  if (!gear || !panel) return;

  function closeMenu() {
    panel.classList.remove('open');
    panel.setAttribute('aria-hidden', 'true');
    gear.setAttribute('aria-expanded', 'false');
  }

  function openMenu() {
    panel.classList.add('open');
    panel.setAttribute('aria-hidden', 'false');
    gear.setAttribute('aria-expanded', 'true');
  }

  gear.addEventListener('click', (e) => {
    e.stopPropagation();
    if (panel.classList.contains('open')) {
      closeMenu();
    } else {
      openMenu();
    }
  });

  document.addEventListener('click', (e) => {
    if (!panel.contains(e.target) && !gear.contains(e.target)) closeMenu();
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
  document.body.classList.remove('role-pending');
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    initLayout();
  });
} else {
  initLayout();
}
