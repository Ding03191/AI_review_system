/***** Drawer *****/
const drawer = document.getElementById('drawer');
const scrim  = document.getElementById('scrim');
const btnOpenDrawer  = document.getElementById('btnOpenDrawer');
const btnCloseDrawer = document.getElementById('btnCloseDrawer');

function openDrawer() {
  drawer.classList.add('open');
  scrim.hidden = false;
  btnOpenDrawer.setAttribute('aria-expanded', 'true');
  drawer.setAttribute('aria-hidden', 'false');
}
function closeDrawer() {
  drawer.classList.remove('open');
  scrim.hidden = true;
  btnOpenDrawer.setAttribute('aria-expanded', 'false');
  drawer.setAttribute('aria-hidden', 'true');
}
btnOpenDrawer.addEventListener('click', openDrawer);
btnCloseDrawer.addEventListener('click', closeDrawer);
scrim.addEventListener('click', closeDrawer);
document.addEventListener('keydown', e=>{ if(e.key==='Escape') closeDrawer(); });

/* 手風琴 */
document.querySelectorAll('.nav-accordion').forEach(btn=>{
  btn.addEventListener('click', ()=>{
    const id = btn.dataset.acc;
    const panel = document.querySelector(`.nav-panel[data-panel="${id}"]`);
    panel.classList.toggle('open');
  });
});

/***** Theme (placeholder) *****/
document.getElementById('btnTheme').addEventListener('click', ()=>alert('外觀切換：目前為亮色（可再加深色）'));

/***** Router *****/
const pages = {
  teacher: document.getElementById('page-teacher'),
  reward : document.getElementById('page-reward'),
  docs   : document.getElementById('page-docs'),
  help   : document.getElementById('page-help'),
  login  : document.getElementById('page-login'),
};
const navLinks = Array.from(document.querySelectorAll('.drawer .nav-item'));
function setActivePage(name){
  Object.entries(pages).forEach(([k,el])=>el.classList.toggle('is-hidden',k!==name));
  navLinks.forEach(a=>a.classList.toggle('is-active',a.dataset.page===name));
  document.querySelector('.hero').style.display = (name==='teacher'||name==='reward')?'flex':'none';
}
function initRoute() {
  const name = (location.hash || '#teacher').replace('#', '');
  setActivePage(pages[name] ? name : 'teacher');
}
window.addEventListener('hashchange', ()=>{ initRoute(); closeDrawer(); });
document.querySelectorAll('[data-page]').forEach(el=>{ el.addEventListener('click', ()=>{}); });
initRoute();

/***** 教師時數：表單 *****/
const formT=document.getElementById('formTeacher');
const filesInput=document.getElementById('files');
const fileList=document.getElementById('fileList');
const msgEl=document.getElementById('msg');
const resultEl=document.getElementById('result');
const previewEl=document.getElementById('preview');
const certNoBox=document.getElementById('certNoBox');

formT?.addEventListener('change',e=>{
  if(e.target.name==='hasCert'){ certNoBox.classList.toggle('is-hidden',e.target.value!=='yes'); }
});
filesInput?.addEventListener('change',()=>{
  fileList.innerHTML='';
  Array.from(filesInput.files).forEach((f,i)=>{
    const li = document.createElement('li');
    li.textContent = `${i + 1}. ${f.name} (${Math.round(f.size / 1024)} KB)`;
    fileList.appendChild(li);
  });
});
function collectTeacherForm(){
  const fd=new FormData(formT);
  return {
    teacherName: fd.get('teacherName')?.toString().trim(),
    department:  fd.get('department')?.toString().trim(),
    teacherId:   fd.get('teacherId')?.toString().trim(),
    ext:         fd.get('ext')?.toString().trim() || null,
    eventDate:   fd.get('eventDate'),
    startTime:   fd.get('startTime'),
    endTime:     fd.get('endTime'),
    courseTitle: fd.get('courseTitle')?.toString().trim(),
    organizer:   fd.get('organizer')?.toString().trim(),
    relevance:   fd.get('relevance')?.toString().trim(),
    hasCert:     fd.get('hasCert'),
    certNo:      (fd.get('hasCert')==='yes' ? (fd.get('certNo')?.toString().trim() || null) : null),
    attachmentCount: filesInput?.files?.length || 0
  };
}
document.getElementById('btnPreview')?.addEventListener('click',()=>{ previewEl.textContent=JSON.stringify(collectTeacherForm(),null,2); });
function validateTeacher(){
  const d=collectTeacherForm(), errs=[];
  if(!d.teacherName) errs.push('請填寫「教師姓名」。');
  if(!d.department)  errs.push('請填寫「任教單位」。');
  if(!d.teacherId)   errs.push('請填寫「教師編號」。');
  if(!d.eventDate)   errs.push('請選擇「活動日期」。');
  if(!d.startTime || !d.endTime) errs.push('請填寫「活動起訖時間」。');
  if(d.startTime && d.endTime && d.startTime>=d.endTime) errs.push('起訖時間不合理。');
  if(!d.courseTitle) errs.push('請填寫「課程名稱」。');
  if(!d.organizer)   errs.push('請填寫「舉辦單位」。');
  if(!d.relevance)   errs.push('請填寫「關聯說明」。');
  if(!d.hasCert)     errs.push('請選擇是否核發證書。');
  if(d.hasCert==='yes' && !d.certNo) errs.push('已選「是」，請填「證書字號」。');
  if(!d.attachmentCount) errs.push('請至少上傳 1 份佐證附件。');
  return errs;
}
formT?.addEventListener('submit',e=>{
  e.preventDefault(); msgEl.textContent=''; resultEl.textContent='';
  const errs=validateTeacher();
  if(errs.length){ msgEl.innerHTML='<span style="color:#dc2626">'+errs.join('<br>')+'</span>'; return; }
  resultEl.innerHTML='<span style="color:#16a34a">（示範）資料已通過前端檢核，可送往後端。</span>';
});

/* OCR 範例呼叫 */
async function fetchJSON(url, body, method='POST'){
  const r=await fetch(url,{method,body}); const ct=r.headers.get('content-type')||'';
  if(!ct.includes('application/json')) throw new Error(`非 JSON 回應 (${r.status})`);
  const j=await r.json(); if(!r.ok || j.ok===false) throw new Error(j.msg||j.error||`HTTP ${r.status}`); return j;
}
document.getElementById('btnOcr')?.addEventListener('click',async()=>{
  if(!filesInput.files?.length){ msgEl.innerHTML='<span style="color:#dc2626">請先選擇檔案</span>'; return; }
  const fd=new FormData(); fd.append('file',filesInput.files[0]);
  try{ const j=await fetchJSON('/api/extract_text',fd); previewEl.textContent='【OCR 範例】\n'+(j.text||'').slice(0,800); }
  catch(err){ msgEl.innerHTML='OCR 錯誤：'+err.message; }
});
document.getElementById('btnOcrGrid')?.addEventListener('click',async()=>{
  if(!filesInput.files?.length){ msgEl.innerHTML='<span style="color:#dc2626">請先選擇檔案</span>'; return; }
  const fd=new FormData(); fd.append('file',filesInput.files[0]);
  try{
    const j=await fetchJSON('/api/extract_structured',fd);
    const f = j.fields || {};
    const set = (n, v) => {
      const el = formT.querySelector(`[name="${n}"]`);
      if (el && v) { el.value = v; el.dispatchEvent(new Event('change', { bubbles: true })); }
    };
    set('teacherName', f.teacher_name);
    set('teacherId', f.teacher_id);
    set('department', f.department);
    set('ext', f.ext);
    set('courseTitle', f.course_title);
    set('organizer', f.organizer);
    set('eventDate', f.event_date);
    set('startTime', f.start_time);
    set('endTime', f.end_time);
    previewEl.textContent = JSON.stringify(f, null, 2);
  } catch (err) {
    msgEl.innerHTML = '表格偵測錯誤：' + err.message;
  }
});

/***** 主題：下拉式多選（含「其他」） *****/
const TOPICS = [
  "材料科學與化學工程",
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

(function buildMultiSelect(){
  const host = document.getElementById('topicMulti');
  if(!host) return;
  host.innerHTML = `
    <button type="button" class="ms-trigger" aria-expanded="false">選擇主題…</button>
    <div class="ms-panel" role="listbox" aria-multiselectable="true">
      <div class="ms-grid" id="msGrid"></div>
      <div id="msOther" class="ms-other is-hidden"><input id="topicOther" placeholder="輸入其他主題"></div>
      <div class="ms-actions"><button type="button" class="btn ghost ms-clear">清除</button><button type="button" class="btn primary ms-apply">套用</button></div>
    </div>`;
  const trigger = host.querySelector('.ms-trigger');
  const panel   = host.querySelector('.ms-panel');
  const grid    = host.querySelector('#msGrid');
  const otherWrap = host.querySelector('#msOther');

  // options
  TOPICS.forEach(t=>{
    const id='opt_'+t.replace(/\s+/g,'');
    const lab=document.createElement('label'); lab.className='ms-opt';
    const cb=document.createElement('input'); cb.type='checkbox'; cb.value=t; cb.id=id;
    const span=document.createElement('span'); span.textContent=t;
    lab.appendChild(cb); lab.appendChild(span); grid.appendChild(lab);
  });

  function updateOther(){
    const hasOther = Array.from(grid.querySelectorAll('input:checked')).some(x=>x.value==='其他');
    otherWrap.classList.toggle('is-hidden', !hasOther);
  }
  grid.addEventListener('change', updateOther);

  function summary(){
    const vals = Array.from(grid.querySelectorAll('input:checked')).map(x=>x.value);
    const other = vals.includes('其他') ? (document.getElementById('topicOther').value.trim() || '其他') : null;
    const names = vals.filter(v=>v!=='其他');
    if(other) names.push('其他:' + other);
    return {vals:names, text: names.length? `已選 ${names.length} 項` : '選擇主題…'};
  }

  // open/close
  const close = ()=>{ panel.classList.remove('open'); trigger.setAttribute('aria-expanded','false'); };
  trigger.addEventListener('click', (e)=>{
    e.stopPropagation();
    panel.classList.toggle('open');
    trigger.setAttribute('aria-expanded', panel.classList.contains('open')?'true':'false');
  });
  document.addEventListener('click', (e)=>{ if(!host.contains(e.target)) close(); });

  // actions
  host.querySelector('.ms-clear').addEventListener('click', ()=>{
    grid.querySelectorAll('input:checked').forEach(cb=>cb.checked=false);
    document.getElementById('topicOther').value='';
    updateOther();
  });
  host.querySelector('.ms-apply').addEventListener('click', ()=>{
    trigger.textContent = summary().text;
    close();
  });
  // init
  trigger.textContent = '選擇主題…';
})();

/***** 送審 *****/
document.getElementById('uploadForm')?.addEventListener('submit',async(e)=>{
  e.preventDefault();
  const form=e.target;
  const file=form.file.files[0];
  if(!file){ alert('請選擇一份 PDF 檔案！'); return; }

  // 取得多選主題
  const grid = document.querySelector('#msGrid');
  const topicOtherInput = document.getElementById('topicOther');
  const chosen = Array.from(grid.querySelectorAll('input:checked')).map(x=>x.value);
  if(chosen.includes('其他') && topicOtherInput.value.trim()){
    chosen[chosen.indexOf('其他')] = '其他:' + topicOtherInput.value.trim();
  }else{
    // 留著單字「其他」或不選都可以
  }

  const instruction = `
學生申請「磨課師學習獎勵」，請根據附件內容比對以下資料是否合格：
編號：${form.caseNo.value}
姓名：${form.name.value}（${form.studentId.value}）
學習項目：${form.project.value}
特色或產業趨勢：${form.feature.value}
永續目標：${form.goals.value}
申請課程：${form.courses.value}
時數總計：${form.totalHours.value}
主題（多選）：${chosen.join(', ')}
請判斷 1) 名稱一致 2) 時間要求 3) 總時數>=12 4) 測驗成績 5) 不得僅國高中生 6) 姓名一致 7) 至少一門符合特色 8) 去重，並以 JSON 回應。`;

  const formData=new FormData();
  formData.append('file',file);
  formData.append('instruction',instruction);
  formData.append('rag','true');

  try{
    const res=await fetch('http://127.0.0.1:5000/python-api/analyzeApplication',{method:'POST',body:formData});
    const data=await res.json();
    if(!res.ok) throw new Error(data.error||'未知錯誤');
    renderAIResponse('feedbackWindow', data);
    renderAIResponse('result', data);
  }catch(err){
    document.getElementById('feedbackWindow').textContent=' '+err.message;
  }
});

/***** Login demo *****/
document.getElementById('formLogin')?.addEventListener('submit',e=>{
  e.preventDefault(); alert('（示範）登入送出；可改為呼叫你的後端 /login。');
});

/** 美化 AI 審核回饋 */
function renderAIResponse(targetId, payload){
  const el = document.getElementById(targetId);
  if(!el) return;

  // 嘗試把字串解析為 JSON
  let data = payload;
  if(typeof payload === 'string'){
    try{ data = JSON.parse(payload); }catch{ data = { raw: payload }; }
  }

  // 抽出常見欄位（容錯）
  const passed   = get(data, ['isPassed','passed','ok'], false);
  const feedback = get(data, ['aiFeedback','feedback','message'], '');
  const name     = get(data, ['applicantName','name'], '');
  const no       = get(data, ['applicantNo','no','caseNo'], '');
  const stdn     = get(data, ['applicantStdn','studentId'], '');
  const date     = get(data, ['applyDate','date'], '');
  const time     = get(data, ['applyTime','time'], '');

  // 其餘欄位（排除已呈現的）
  const shownKeys = new Set(['aiFeedback','feedback','message','isPassed','passed','ok','applicantName','name','applicantNo','no','caseNo','applicantStdn','studentId','applyDate','date','applyTime','time']);
  const others = Object.entries(data).filter(([k])=>!shownKeys.has(k));

  // 建立 DOM
  const root = document.createElement('div'); root.className='fbx';
  // header
  const hd = document.createElement('div'); hd.className='fbx-hd';
  const pill = document.createElement('span'); pill.className='pill '+(passed?'ok':'ng');
  pill.textContent = passed ? '通過' : '未通過';
  const title = document.createElement('strong'); title.textContent='審核結果';
  hd.appendChild(pill); hd.appendChild(title); root.appendChild(hd);

  // summary
  if(feedback){
    const sum = document.createElement('div'); sum.className='fbx-summary';
    sum.textContent = feedback;
    root.appendChild(sum);
  }

  // key-values
  const kv = document.createElement('div'); kv.className='kv';
  const addKV = (k,v)=>{
  if(v===undefined || v===null || v==='') return;
  const dk=document.createElement('div'); dk.className='k'; dk.textContent=k;
  const dv=document.createElement('div'); dv.className='v'; dv.textContent=String(v);
  kv.appendChild(dk); kv.appendChild(dv);
};
  addKV('申請人', name);
  addKV('案件編號', no);
  addKV('學號/身分', stdn);
  addKV('申請日期', date);
  addKV('申請時間', time);
  // 其他欄位
  others.forEach(([k,v])=> addKV(k, typeof v==='object' ? JSON.stringify(v) : String(v)));
  root.appendChild(kv);

  // 原始 JSON（可複製）
  const raw = document.createElement('div');
  raw.className='codewrap';
  const pre = document.createElement('pre');
  pre.textContent = JSON.stringify(data, null, 2);
  raw.appendChild(pre);
  const actions = document.createElement('div'); actions.className='fbx-actions';
  const copyBtn = document.createElement('button'); copyBtn.className='btn copy'; copyBtn.type='button'; copyBtn.textContent='複製 JSON';
  copyBtn.addEventListener('click', ()=>{
    navigator.clipboard.writeText(pre.textContent).then(()=>{ copyBtn.textContent='已複製'; setTimeout(()=>copyBtn.textContent='複製 JSON',1200); });
  });
  actions.appendChild(copyBtn);

  // 清空並放入
  el.innerHTML='';
  el.appendChild(root);
  el.appendChild(actions);

  // 工具：安全取得多層值
  function get(obj, keys, def){ for(const k of keys){ if(obj && Object.prototype.hasOwnProperty.call(obj,k)) return obj[k]; } return def; }
}

