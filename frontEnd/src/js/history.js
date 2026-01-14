// API base: read from meta[name="api-base"], fallback to same origin
const API_BASE = (function(){
  try{
    const m = document.querySelector('meta[name="api-base"]');
    if (m && m.content) return m.content.replace(/\/+$/,'');
  }catch(e){}
  return location.origin;
})();

(function initRecordQuery(){
  const form = document.getElementById('recordQueryForm');
  const dateInput = document.getElementById('recordDate');
  const listEl = document.getElementById('recordList');
  const totalEl = document.getElementById('summaryTotal');
  const passedEl = document.getElementById('summaryPassed');
  const failedEl = document.getElementById('summaryFailed');
  if (!form || !dateInput || !listEl || !totalEl || !passedEl || !failedEl) return;

  function setSummary(total, passed, failed){
    totalEl.textContent = String(total);
    passedEl.textContent = String(passed);
    failedEl.textContent = String(failed);
  }

  function toLocalDateInputValue(date){
    const local = new Date(date);
    local.setMinutes(local.getMinutes() - local.getTimezoneOffset());
    return local.toISOString().slice(0, 10);
  }

  function renderEmpty(message, colSpan){
    listEl.innerHTML = '';
    const tr = document.createElement('tr');
    const td = document.createElement('td');
    td.colSpan = colSpan;
    td.className = 'empty';
    td.textContent = message;
    tr.appendChild(td);
    listEl.appendChild(tr);
  }

  async function fetchRecords(date){
    const res = await fetch(`${API_BASE}/api/query_records?date=${encodeURIComponent(date)}`,
      { method: 'GET', credentials: 'include' }
    );
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    return data;
  }

  function renderRows(records){
    listEl.innerHTML = '';
    records.forEach((rec)=>{
      const tr = document.createElement('tr');
      const cells = [
        rec.applyTime || '-',
        rec.applicantName || '-',
        rec.applicantNo ?? '-',
        rec.applicantStdn || '-'
      ];
      cells.forEach((val)=>{
        const td = document.createElement('td');
        td.textContent = String(val);
        tr.appendChild(td);
      });

      const statusTd = document.createElement('td');
      const passed = !!rec.isPassed;
      statusTd.textContent = passed ? '通過' : '未通過';
      statusTd.className = passed ? 'status-pass' : 'status-fail';
      tr.appendChild(statusTd);

      const feedbackTd = document.createElement('td');
      feedbackTd.className = 'feedback';
      feedbackTd.textContent = rec.aiFeedback || '-';
      tr.appendChild(feedbackTd);

      const fileTd = document.createElement('td');
      if (rec.pdf_path){
        const link = document.createElement('a');
        link.href = `${API_BASE}/${String(rec.pdf_path).replace(/^\//,'')}`;
        link.textContent = '下載';
        link.target = '_blank';
        link.rel = 'noopener';
        fileTd.appendChild(link);
      } else {
        fileTd.textContent = '-';
      }
      tr.appendChild(fileTd);

      listEl.appendChild(tr);
    });
  }

  form.addEventListener('submit', async (e)=>{
    e.preventDefault();
    const date = dateInput.value;
    if (!date) {
      renderEmpty('請選擇日期', 7);
      setSummary('-', '-', '-');
      return;
    }
    renderEmpty('查詢中…', 7);
    try{
      const data = await fetchRecords(date);
      setSummary(data.total || 0, data.passed || 0, data.failed || 0);
      if (!data.records || data.records.length === 0){
        renderEmpty('查無資料', 7);
        return;
      }
      renderRows(data.records);
    }catch(err){
      renderEmpty(err.message || '查詢失敗', 7);
      setSummary('-', '-', '-');
    }
  });

  if (!dateInput.value){
    dateInput.value = toLocalDateInputValue(new Date());
  }
})();
