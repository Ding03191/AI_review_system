const API_BASE = (function(){
  try{
    const m = document.querySelector('meta[name="api-base"]');
    if (m && m.content) return m.content.replace(/\/+$/,'');
  }catch(e){}
  return location.origin;
})();

const form = document.getElementById('reviewForm');
const resultEl = document.getElementById('reviewResult');

function renderResult(data){
  if (!resultEl) return;
  resultEl.innerHTML = '';

  const normalizeBool = (value)=>{
    if (typeof value === 'string') return value.toLowerCase() === 'true';
    return Boolean(value);
  };

  const passed = normalizeBool(data?.isPassed);
  const statusText = passed ? '通過' : '不通過';

  const wrap = document.createElement('div');
  const statusEl = document.createElement('div');
  statusEl.className = 'review-status';
  statusEl.textContent = `審核結果：${statusText}`;
  statusEl.classList.add(passed ? 'is-pass' : 'is-fail');

  const reasonTitle = document.createElement('div');
  reasonTitle.className = 'review-label';
  reasonTitle.textContent = '原因';

  const reasonEl = document.createElement('pre');
  reasonEl.className = 'review-reason';
  reasonEl.textContent = data?.aiFeedback || '無';

  const info = document.createElement('div');
  info.className = 'review-meta';

  const nameRow = document.createElement('div');
  nameRow.textContent = `姓名：${data?.applicantName || '-'}`;

  const dateRow = document.createElement('div');
  dateRow.textContent = `申請日期：${data?.applyDate || '-'}`;

  const timeRow = document.createElement('div');
  timeRow.textContent = `申請時間：${data?.applyTime || '-'}`;

  info.appendChild(nameRow);
  info.appendChild(dateRow);
  info.appendChild(timeRow);

  wrap.appendChild(statusEl);
  wrap.appendChild(reasonTitle);
  wrap.appendChild(reasonEl);
  wrap.appendChild(info);
  resultEl.appendChild(wrap);
}

function renderError(message){
  if (!resultEl) return;
  resultEl.textContent = message || '送出失敗';
}

/* ===== Course list ===== */
(function courseListModule(){
  const list = document.getElementById('courseList');
  const addBtn = document.getElementById('addCourseBtn');
  if (!list || !addBtn) return;

  function addRow(value = ''){
    const row = document.createElement('div');
    row.className = 'course-row';
    row.innerHTML = `
      <input type="text" name="courses" placeholder="輸入課程名稱" value="${value}">
      <button type="button" class="icon-btn sm course-remove" aria-label="移除課程">-</button>
    `;
    list.appendChild(row);
    row.querySelector('input').focus();
  }

  document.addEventListener('click', (e)=>{
    if (e.target.closest('#addCourseBtn')) addRow();
    const rm = e.target.closest('.course-remove');
    if (rm) {
      const rows = list.querySelectorAll('.course-row');
      if (rows.length > 1) rm.closest('.course-row').remove();
    }
  });

  document.addEventListener('keydown', (e)=>{
    if (e.key !== 'Enter') return;
    if (!e.target.matches('#courseList input[name="courses"]')) return;
    e.preventDefault();
    addRow();
  });
})();

/* ===== SDG multi-select ===== */
const SDG_OPTIONS = [
  {v:"1",t:"SDG 1 消除貧窮"},
  {v:"2",t:"SDG 2 消除飢餓"},
  {v:"3",t:"SDG 3 健康與福祉"},
  {v:"4",t:"SDG 4 教育品質"},
  {v:"5",t:"SDG 5 性別平等"},
  {v:"6",t:"SDG 6 淨水與衛生"},
  {v:"7",t:"SDG 7 可負擔能源"},
  {v:"8",t:"SDG 8 就業與經濟成長"},
  {v:"9",t:"SDG 9 工業、創新基礎建設"},
  {v:"10",t:"SDG 10 減少不平等"},
  {v:"11",t:"SDG 11 永續城市"},
  {v:"12",t:"SDG 12 責任消費與生產"},
  {v:"13",t:"SDG 13 氣候行動"},
  {v:"14",t:"SDG 14 海洋生態"},
  {v:"15",t:"SDG 15 陸地生態"},
  {v:"16",t:"SDG 16 和平與正義制度"},
  {v:"17",t:"SDG 17 全球夥伴"}
];

(function buildSDGMulti(){
  const host = document.getElementById('sdgMulti');
  const hiddenInput = document.getElementById('sdg_values');
  const chosenWrap = document.getElementById('sdgChosen');
  if (!host || !hiddenInput || !chosenWrap) return;

  host.innerHTML = `
    <button type="button" class="ms-trigger" aria-expanded="false">選擇永續目標</button>
    <div class="ms-panel" role="listbox" aria-multiselectable="true">
      <div class="ms-grid" id="sdgGrid"></div>
      <div class="ms-actions">
        <button type="button" class="btn ghost sdg-clear">清除</button>
        <button type="button" class="btn primary sdg-apply">套用</button>
      </div>
    </div>
  `;

  const trigger = host.querySelector('.ms-trigger');
  const panel = host.querySelector('.ms-panel');
  const grid = host.querySelector('#sdgGrid');

  SDG_OPTIONS.forEach(o=>{
    const lab = document.createElement('label'); lab.className='ms-opt';
    const cb = document.createElement('input'); cb.type='checkbox'; cb.value=o.v; cb.dataset.text=o.t;
    const span = document.createElement('span'); span.textContent=o.t;
    lab.appendChild(cb); lab.appendChild(span); grid.appendChild(lab);
  });

  const close = ()=>{ panel.classList.remove('open'); trigger.setAttribute('aria-expanded','false'); };
  trigger.addEventListener('click', e=>{
    e.stopPropagation();
    panel.classList.toggle('open');
    trigger.setAttribute('aria-expanded', panel.classList.contains('open') ? 'true' : 'false');
  });
  document.addEventListener('click', e=>{ if(!host.contains(e.target)) close(); });

  function collect(){
    const cbs = Array.from(grid.querySelectorAll('input:checked'));
    return {vals: cbs.map(cb=>cb.value), txts: cbs.map(cb=>cb.dataset.text)};
  }

  host.querySelector('.sdg-apply').addEventListener('click', ()=>{
    const {vals, txts} = collect();
    hiddenInput.value = vals.join(',');
    trigger.textContent = vals.length ? '已選 {n} 項'.replace('{n}', vals.length) : '選擇永續目標';
    chosenWrap.innerHTML = txts.map(t=>`<span class="tag">${t}</span>`).join(' ');
    close();
  });

  host.querySelector('.sdg-clear').addEventListener('click', ()=>{
    grid.querySelectorAll('input:checked').forEach(cb=>cb.checked=false);
    hiddenInput.value = '';
    trigger.textContent = '選擇永續目標';
    chosenWrap.innerHTML = '';
  });
})();

/* ===== Topic multi-select ===== */
const TOPICS = [
  "材料科學與化學工程",
  "機械設計與製造自動化",
  "冷凍空調與能源技術",
  "智慧製造與機電整合應用",
  "積體電路與多媒體技術",
  "數據分析與 AI 應用",
  "智慧嵌入式系統",
  "文創設計與行銷",
  "景觀設計與工程施作",
  "英語商務溝通與管理",
  "產業自動化與管理",
  "企業經營與管理",
  "行銷策略與市場分析",
  "系統資訊化及專案管理",
  "健康產業及運動科技",
  "永續發展與綠色科技",
  "其他"
];

(function buildTopicMulti(){
  const host = document.getElementById('topicMulti');
  if (!host) return;
  host.innerHTML = `
    <button type="button" class="ms-trigger" aria-expanded="false">選擇課程主題</button>
    <div class="ms-panel" role="listbox" aria-multiselectable="true">
      <div class="ms-grid" id="topicGrid"></div>
      <div id="topicOtherWrap" class="ms-other is-hidden"><input id="topicOther" placeholder="輸入其他主題"></div>
      <div class="ms-actions"><button type="button" class="btn ghost topic-clear">清除</button><button type="button" class="btn primary topic-apply">套用</button></div>
    </div>`;

  const trigger = host.querySelector('.ms-trigger');
  const panel = host.querySelector('.ms-panel');
  const grid = host.querySelector('#topicGrid');
  const otherWrap = host.querySelector('#topicOtherWrap');

  TOPICS.forEach(t=>{
    const lab = document.createElement('label'); lab.className='ms-opt';
    const cb = document.createElement('input'); cb.type='checkbox'; cb.value=t;
    const span = document.createElement('span'); span.textContent=t;
    lab.appendChild(cb); lab.appendChild(span); grid.appendChild(lab);
  });

  function updateOther(){
    const hasOther = Array.from(grid.querySelectorAll('input:checked')).some(x=>x.value==='其他');
    otherWrap.classList.toggle('is-hidden', !hasOther);
  }
  grid.addEventListener('change', updateOther);

  const close = ()=>{ panel.classList.remove('open'); trigger.setAttribute('aria-expanded','false'); };
  trigger.addEventListener('click', (e)=>{
    e.stopPropagation();
    panel.classList.toggle('open');
    trigger.setAttribute('aria-expanded', panel.classList.contains('open')?'true':'false');
  });
  document.addEventListener('click', (e)=>{ if(!host.contains(e.target)) close(); });

  function summary(){
    const vals = Array.from(grid.querySelectorAll('input:checked')).map(x=>x.value);
    const other = vals.includes('其他') ? (document.getElementById('topicOther').value.trim() || '其他') : null;
    const names = vals.filter(v=>v!=='其他');
    if(other) names.push('其他:' + other);
    return {vals:names, text: names.length? '已選 {n} 項'.replace('{n}', names.length) : '選擇課程主題'};
  }

  host.querySelector('.topic-clear').addEventListener('click', ()=>{
    grid.querySelectorAll('input:checked').forEach(cb=>cb.checked=false);
    document.getElementById('topicOther').value='';
    updateOther();
  });
  host.querySelector('.topic-apply').addEventListener('click', ()=>{
    trigger.textContent = summary().text;
    close();
  });
})();

/* ===== Submit ===== */
form?.addEventListener('submit', async (e)=>{
  e.preventDefault();
  if (!form) return;
  const fd = new FormData(form);
  try{
    resultEl.textContent = '送出中…';
    const res = await fetch(`${API_BASE}/python-api/analyzeApplication`, {
      method: 'POST',
      body: fd
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    renderResult(data);
  }catch(err){
    renderError(err.message || '送出失敗');
  }
});
