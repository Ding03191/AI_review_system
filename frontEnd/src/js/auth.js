// auth.js: login/register only
const API_BASE = (function(){
  try{
    const m = document.querySelector('meta[name="api-base"]');
    if (m && m.content) return m.content.replace(/\/+$/,'');
  }catch(e){}
  return 'http://127.0.0.1:5000';
})();

async function apiLogin(email, password){
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: 'POST',
    credentials: 'include',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ email, password })
  });
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || '????');
  return data.data.user;
}

async function apiRegister(name, email, password){
  const res = await fetch(`${API_BASE}/api/auth/register`, {
    method: 'POST',
    credentials: 'include',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ name, email, password })
  });
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || '????');
  return data.data || {};
}

function bindPasswordToggles(){
  document.querySelectorAll('.icon-btn[data-toggle]').forEach(btn=>{
    btn.addEventListener('click', ()=>{
      const t = document.querySelector(btn.dataset.toggle);
      if (t) t.type = (t.type === 'password') ? 'text' : 'password';
    });
  });
}

function initLogin(){
  const loginForm = document.getElementById('formLogin');
  if (!loginForm) return;
  const err = document.getElementById('loginError');
  loginForm.addEventListener('submit', async (e)=>{
    e.preventDefault();
    const fd = new FormData(loginForm);
    const email = fd.get('account');
    const pwd = fd.get('password');
    const btn = loginForm.querySelector('button[type="submit"]');
    err.textContent = '';
    btn.disabled = true; btn.dataset.loading = 'true';
    try{
      await apiLogin(email, pwd);
      location.href = 'index.html';
    }catch(ex){
      err.textContent = ex.message || '????';
    }finally{
      btn.disabled = false; btn.dataset.loading = '';
    }
  });
}

function initRegister(){
  const registerForm = document.getElementById('formRegister');
  if (!registerForm) return;
  const err = document.getElementById('registerError');
  registerForm.addEventListener('submit', async (e)=>{
    e.preventDefault();
    const fd = new FormData(registerForm);
    const name = fd.get('name')?.toString().trim();
    const email= fd.get('email')?.toString().trim();
    const pwd  = fd.get('password')?.toString();
    const btn  = registerForm.querySelector('button[type="submit"]');
    err.textContent=''; btn.disabled=true; btn.dataset.loading='true';
    try{
      if (!/.+@.+\..+/.test(email)) throw new Error('Email ????');
      if ((pwd||'').length < 6) throw new Error('???? 6 ?');
      await apiRegister(name, email, pwd);
      location.href = 'login.html';
    }catch(ex){
      err.textContent = ex.message || '????';
    }finally{
      btn.disabled=false; btn.dataset.loading='';
    }
  });
}

bindPasswordToggles();
initLogin();
initRegister();
