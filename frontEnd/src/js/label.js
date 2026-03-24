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

const API_BASE = resolveApiBase();

const STATUS_LABELS = {
  submitted: '\u5df2\u9001\u51fa',
  reviewing: '\u5be9\u6838\u4e2d',
  approved: '\u5be9\u6838\u901a\u904e',
  rejected: '\u5be9\u6838\u4e0d\u901a\u904e',
  returned: '\u5df2\u9000\u56de',
};

const state = {
  unlabeled: [],
  labeled: [],
  activeTab: 'unlabeled',
  loading: false,
};

function initTabFromQuery() {
  const q = new URLSearchParams(location.search);
  const tab = (q.get('tab') || '').trim();
  if (tab === 'labeled' || tab === 'unlabeled') {
    state.activeTab = tab;
  }
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function toDetailUrl(rec, sourceTab) {
  const q = new URLSearchParams({
    applicantStdn: rec.applicantStdn || '',
    applicantNo: String(rec.applicantNo ?? ''),
    source: sourceTab || 'unlabeled',
  });
  return `label_detail.html?${q.toString()}`;
}

function formatReviewStatus(status) {
  return STATUS_LABELS[status] || STATUS_LABELS.reviewing;
}

function renderCards(listEl, emptyEl, records, sourceTab) {
  if (!listEl || !emptyEl) return;
  listEl.innerHTML = '';
  if (!records.length) {
    emptyEl.style.display = 'block';
    return;
  }
  emptyEl.style.display = 'none';

  records.forEach((rec) => {
    const card = el('button', 'label-card', '');
    card.type = 'button';
    card.classList.add('label-info-card');
    card.dataset.key = `${rec.applicantStdn || ''}-${rec.applicantNo || ''}`;

    const caseNo = el('div', 'label-info-line', `Case: ${rec.applicantNo ?? '-'}`);
    const name = el('div', 'label-info-line', `${rec.applicantName || '-'} (${rec.applicantStdn || '-'})`);
    const aiStatus = el('span', `pill ${rec.isPassed ? 'ok' : 'ng'}`, rec.isPassed ? 'AI PASS' : 'AI FAIL');
    aiStatus.classList.add('label-card-badge');
    const review = el('div', 'label-info-line', `${formatReviewStatus(rec.reviewStatus)}`);
    const datetime = el('div', 'label-info-line', `${rec.applyDate || '-'} ${rec.applyTime || ''}`);

    if (sourceTab === 'labeled') {
      const marked = el('span', 'pill ok label-marked-pill', 'Submitted');
      card.appendChild(marked);
    }
    card.appendChild(caseNo);
    card.appendChild(name);
    card.appendChild(aiStatus);
    card.appendChild(review);
    card.appendChild(datetime);
    card.addEventListener('click', () => {
      location.href = toDetailUrl(rec, sourceTab);
    });
    listEl.appendChild(card);
  });
}

function renderLists() {
  renderCards(
    document.getElementById('unlabeledList'),
    document.getElementById('unlabeledEmpty'),
    state.unlabeled,
    'unlabeled'
  );
  renderCards(
    document.getElementById('labeledList'),
    document.getElementById('labeledEmpty'),
    state.labeled,
    'labeled'
  );
}

function updateTabUi() {
  const isUnlabeled = state.activeTab === 'unlabeled';
  const tabUnlabeled = document.getElementById('tabUnlabeled');
  const tabLabeled = document.getElementById('tabLabeled');
  const panelUnlabeled = document.getElementById('panelUnlabeled');
  const panelLabeled = document.getElementById('panelLabeled');
  if (tabUnlabeled) tabUnlabeled.classList.toggle('active', isUnlabeled);
  if (tabLabeled) tabLabeled.classList.toggle('active', !isUnlabeled);
  if (panelUnlabeled) panelUnlabeled.classList.toggle('is-hidden', !isUnlabeled);
  if (panelLabeled) panelLabeled.classList.toggle('is-hidden', isUnlabeled);
}

async function loadRecords() {
  if (state.loading) return;
  state.loading = true;
  try {
    const [unlabeledRes, labeledRes] = await Promise.all([
      fetch(`${API_BASE}/api/labeling/unlabeled?limit=500&offset=0`, { credentials: 'include' }),
      fetch(`${API_BASE}/api/labeling/labeled?limit=500&offset=0`, { credentials: 'include' }),
    ]);
    const unlabeledData = await unlabeledRes.json();
    const labeledData = await labeledRes.json();
    if (!unlabeledRes.ok) throw new Error(unlabeledData.error || `HTTP ${unlabeledRes.status}`);
    if (!labeledRes.ok) throw new Error(labeledData.error || `HTTP ${labeledRes.status}`);
    state.unlabeled = unlabeledData.records || [];
    state.labeled = labeledData.records || [];
    renderLists();
  } catch (err) {
    const listEl = document.getElementById('unlabeledList');
    if (listEl) listEl.textContent = err.message || 'Load failed.';
  } finally {
    state.loading = false;
  }
}

async function exportExcel() {
  try {
    const res = await fetch(`${API_BASE}/api/labeling/export_excel`, { credentials: 'include' });
    if (!res.ok) {
      const data = await res.json();
      throw new Error(data.error || `HTTP ${res.status}`);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'review_export.xlsx';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch (err) {
    alert(err.message || 'Export failed');
  }
}

function bindEvents() {
  const tabUnlabeled = document.getElementById('tabUnlabeled');
  const tabLabeled = document.getElementById('tabLabeled');
  const btnReload = document.getElementById('btnReloadLabel');
  const btnExport = document.getElementById('btnExportLabel');

  if (tabUnlabeled) {
    tabUnlabeled.addEventListener('click', () => {
      state.activeTab = 'unlabeled';
      updateTabUi();
    });
  }
  if (tabLabeled) {
    tabLabeled.addEventListener('click', () => {
      state.activeTab = 'labeled';
      updateTabUi();
    });
  }
  if (btnReload) {
    btnReload.addEventListener('click', () => {
      loadRecords();
    });
  }
  if (btnExport) {
    btnExport.addEventListener('click', () => {
      exportExcel();
    });
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    initTabFromQuery();
    bindEvents();
    updateTabUi();
    loadRecords();
  });
} else {
  initTabFromQuery();
  bindEvents();
  updateTabUi();
  loadRecords();
}
