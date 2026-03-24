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

const COL_ITEM = '\u9805\u76ee';
const COL_LLM = 'LLM\u8fa8\u8b58\u5230\u7d50\u679c';
const COL_PASS = '\u7b26\u5408';
const COL_FAIL = '\u4e0d\u7b26\u5408';
const COL_REASON = '\u539f\u56e0';
const COL_OTHER = '\u5176\u5b83';

const FIELD_ORDER = ['name', 'course', 'period', 'exam', 'target'];
const FIELD_META = {
  name: { label: '\u4e2d\u6587\u59d3\u540d', keywords: ['\u4e2d\u6587\u59d3\u540d', '\u7533\u8acb\u4eba\u59d3\u540d', '\u8b49\u66f8\u59d3\u540d', '\u59d3\u540d'] },
  course: { label: '\u8ab2\u7a0b\u540d\u7a31', keywords: ['\u8ab2\u7a0b\u540d\u7a31', '\u8ab2\u7a0b'] },
  period: { label: '\u8ab2\u7a0b\u671f\u9593', keywords: ['\u8ab2\u7a0b\u671f\u9593', '\u958b\u8ab2\u671f\u9593'] },
  exam: { label: '\u6709\u7121\u6e2c\u9a57', keywords: ['\u6709\u7121\u6e2c\u9a57', '\u6e2c\u9a57', '\u6e2c\u9a57\u6210\u7e3e'] },
  target: { label: '\u9069\u7528\u5c0d\u8c61', keywords: ['\u9069\u7528\u5c0d\u8c61'] },
};

const MISSING_ITEM_TEXT = '未抓取到這個項目';
const DISPLAY_MISSING_TEXT = '未找到';

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function textOf(value) {
  if (value === null || value === undefined) return '';
  return String(value).trim();
}

function isBlank(value) {
  const text = textOf(value);
  return !text || text === '-' || text === 'null' || text === 'undefined';
}

function isMarked(value) {
  const text = textOf(value).toLowerCase();
  return ['\u25cb', '\u25ef', 'o', 'yes', 'y', 'true', '1', 'pass', 'passed', '\u7b26\u5408', '\u662f'].includes(text);
}

function isFalseMark(value) {
  const text = textOf(value).toLowerCase();
  return ['\u5426', 'no', 'n', 'false', '0'].includes(text);
}

function pickFirst(row, keys) {
  if (!row || typeof row !== 'object') return '';
  for (const key of keys) {
    if (key in row && !isBlank(row[key])) return textOf(row[key]);
  }
  const lowered = Object.fromEntries(Object.keys(row).map((key) => [key.toLowerCase(), key]));
  for (const key of keys) {
    const actual = lowered[key.toLowerCase()];
    if (actual && !isBlank(row[actual])) return textOf(row[actual]);
  }
  return '';
}

function inferFieldKey(...parts) {
  const joined = parts.map(textOf).join(' ');
  const fieldKeys = ['period', 'exam', 'target', 'name', 'course'];
  for (const fieldKey of fieldKeys) {
    const meta = FIELD_META[fieldKey];
    if (meta.keywords.some((keyword) => joined.includes(keyword))) return fieldKey;
  }
  return '';
}

function createEntry(fieldKey, value = '', status = 'other', note = '') {
  return { fieldKey, value: textOf(value), status, note: textOf(note) };
}

function extractNameValue(...parts) {
  const joined = parts.map(textOf).join('\n');
  const matches = [...joined.matchAll(/([\u4e00-\u9fff]{2,4})/g)].map((match) => match[1]);
  return matches.find((value) => !['\u4e2d\u6587\u59d3\u540d', '\u7533\u8acb\u4eba\u59d3\u540d', '\u8b49\u66f8\u59d3\u540d', '\u59d3\u540d'].includes(value)) || '';
}

function cleanCourseLine(line) {
  let value = textOf(line);
  if (!value) return '';
  value = value.replace(/^[^:：]*[:：]\s*/, '');
  value = value.replace(/[，,]\s*(\u8a8d\u8b49\u6642\u6578|\u6e2c\u9a57\u6210\u7e3e|\u9069\u7528\u5c0d\u8c61|\u7e3d\u6642\u6578).*/, '');
  value = value.replace(/\s*(\u8a8d\u8b49\u6642\u6578|\u6e2c\u9a57\u6210\u7e3e|\u9069\u7528\u5c0d\u8c61|\u7e3d\u6642\u6578)\s*[:：].*/, '');
  value = value.trim();
  if (!value) return '';
  if (/^(\u8207\u8b49\u66f8|\u540c\u4e00\u7533\u8acb|\u672a\u63d0\u4f9b|\u7121\u6cd5\u78ba\u8a8d|\u4e0d\u901a\u904e|\u901a\u904e\u539f\u56e0|\u4e0d\u901a\u904e\u539f\u56e0)/.test(value)) return '';
  return value;
}

function extractCourseValues(...parts) {
  const source = parts.map(textOf).join('\n');
  const lines = source.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  const values = [];

  lines.forEach((line) => {
    if (/^\u8ab2\u7a0b\d+\s*[:：]/.test(line) || /^\u8ab2\u7a0b\u540d\u7a31\s*[:：]/.test(line)) {
      const course = cleanCourseLine(line);
      if (course && !values.includes(course)) values.push(course);
    }
  });

  return values;
}

function extractGenericValue(fieldKey, ...parts) {
  const source = parts.map(textOf).join('\n');
  for (const keyword of FIELD_META[fieldKey].keywords) {
    const match = source.match(new RegExp(`${keyword}\\s*[:：]\\s*([^\\n]+)`));
    if (match) return textOf(match[1]);
  }
  return '';
}

function splitLines(value) {
  return textOf(value)
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line && !isMissingItem(line));
}

function isMissingItem(value) {
  const text = textOf(value);
  return text === MISSING_ITEM_TEXT
    || text === DISPLAY_MISSING_TEXT
    || /(未抓取|未擷取|未檢測).*?項目/.test(text)
    || /未找到/.test(text);
}

function hasMissingItemText(value) {
  return /(未抓取|未擷取|未檢測).*?項目/.test(textOf(value)) || /未找到/.test(textOf(value));
}

function mergeUniqueText(existing, incoming) {
  const values = [...splitLines(existing), ...splitLines(incoming)];
  return [...new Set(values)].join('\n');
}

function resolveFieldValue(fieldKey, resultText, itemText, context = {}) {
  if (isMissingItem(resultText) || hasMissingItemText(itemText)) return '';
  if (fieldKey === 'name') return extractNameValue(resultText, itemText) || textOf(resultText) || textOf(context.applicantName);
  if (fieldKey === 'course') {
    const extracted = extractCourseValues(resultText, itemText).join('\n');
    return extracted || (isMissingItem(resultText) ? '' : textOf(resultText));
  }
  if (fieldKey === 'period' || fieldKey === 'exam' || fieldKey === 'target') {
    const extracted = extractGenericValue(fieldKey, resultText, itemText);
    return extracted || (isMissingItem(resultText) ? '' : textOf(resultText));
  }
  return textOf(resultText);
}

function mergeEntry(existing, incoming, fieldKey) {
  if (!existing) return incoming;

  const mergedValue = fieldKey === 'name'
    ? (existing.value || incoming.value)
    : mergeUniqueText(existing.value, incoming.value);

  let status = existing.status;
  if (incoming.status === 'fail') status = 'fail';
  else if (incoming.status === 'pass' && status !== 'fail') status = 'pass';
  else if (!mergedValue && incoming.status === 'other' && status !== 'fail' && status !== 'pass') status = 'other';

  const note = status === 'fail'
    ? (incoming.note || existing.note)
    : (existing.note && existing.note !== '\u672a\u6293\u53d6\u5230\u9019\u500b\u9805\u76ee' ? existing.note : incoming.note);

  return {
    value: mergedValue,
    status,
    note: note || '\u672a\u6293\u53d6\u5230\u9019\u500b\u9805\u76ee',
  };
}

function coerceRows(rawRows) {
  if (Array.isArray(rawRows)) return rawRows;
  if (typeof rawRows === 'string') {
    try {
      const parsed = JSON.parse(rawRows);
      if (Array.isArray(parsed)) return parsed;
    } catch (e) {}
  }
  return [];
}

function expandPackedRows(rawRows) {
  const rows = Array.isArray(rawRows) ? rawRows : [];
  const expanded = [];
  const expectedItems = ['\u4e2d\u6587\u59d3\u540d', '\u8ab2\u7a0b\u540d\u7a31', '\u8ab2\u7a0b\u671f\u9593', '\u6709\u7121\u6e2c\u9a57', '\u9069\u7528\u5c0d\u8c61'];

  rows.forEach((row) => {
    const itemText = pickFirst(row, ['item', 'Item', '\u9805\u76ee', '\u8fa8\u8b58\u9805\u76ee']);
    const resultText = pickFirst(row, ['result', 'Result', 'LLM Result', 'LLM\u8fa8\u8b58\u5230\u7d50\u679c', '\u8fa8\u8b58\u7d50\u679c']);
    const passText = pickFirst(row, ['pass', 'Pass', '\u7b26\u5408', 'isPass', 'isPassed']) || '-';
    const failText = pickFirst(row, ['fail', 'Fail', '\u4e0d\u7b26\u5408']) || '-';
    const otherText = pickFirst(row, ['other', 'Other', '\u5176\u5b83', '\u5176\u4ed6']) || '-';

    const itemParts = itemText.split(/[|、]/).map((part) => part.trim()).filter(Boolean);
    const resultParts = resultText.split(/[|、]/).map((part) => part.trim());
    if (itemParts.length === expectedItems.length && expectedItems.every((item, index) => itemParts[index] === item)) {
      expectedItems.forEach((item, index) => {
        const value = resultParts[index] || '';
        expanded.push({
          item,
          result: value === '\u672a\u6293\u53d6\u5230\u9019\u500b\u9805\u76ee' ? '' : value,
          pass: value && value !== '\u672a\u6293\u53d6\u5230\u9019\u500b\u9805\u76ee' ? passText : '-',
          fail: failText,
          other: value && value !== '\u672a\u6293\u53d6\u5230\u9019\u500b\u9805\u76ee' ? '-' : otherText,
        });
      });
      return;
    }

    expanded.push(row);
  });

  return expanded;
}

function normalizeFeedbackRows(rawRows, feedbackText, context = {}) {
  const rows = expandPackedRows(coerceRows(rawRows));
  const bucket = Object.fromEntries(FIELD_ORDER.map((fieldKey) => [fieldKey, null]));

  const ingest = (itemText, resultText, passText, failText, otherText, reasonText) => {
    const fieldKey = inferFieldKey(itemText, resultText);
    if (!fieldKey) return;

    const value = resolveFieldValue(fieldKey, resultText, itemText, context);
    const missingItem = isMissingItem(resultText)
      || isMissingItem(otherText)
      || isMissingItem(reasonText)
      || hasMissingItemText(itemText);
    const failed = !isMarked(passText)
      && (isMarked(failText) || (!isBlank(failText) && !isFalseMark(failText)) || !isBlank(reasonText));
    const entry = {
      value,
      status: value ? (failed ? 'fail' : 'pass') : (missingItem ? 'fail' : 'other'),
      note: missingItem
        ? '\u672a\u6293\u53d6\u5230\u9019\u500b\u9805\u76ee'
        : (failed ? (failText && !isMarked(failText) ? failText : reasonText) : (otherText || '\u672a\u6293\u53d6\u5230\u9019\u500b\u9805\u76ee')),
    };
    bucket[fieldKey] = mergeEntry(bucket[fieldKey], entry, fieldKey);
  };

  rows.forEach((row) => {
    ingest(
      pickFirst(row, ['item', 'Item', '\u9805\u76ee', '\u8fa8\u8b58\u9805\u76ee']),
      pickFirst(row, ['result', 'Result', 'LLM Result', 'LLM\u8fa8\u8b58\u5230\u7d50\u679c', '\u8fa8\u8b58\u7d50\u679c']),
      pickFirst(row, ['pass', 'Pass', '\u7b26\u5408', 'isPass', 'isPassed']),
      pickFirst(row, ['fail', 'Fail', '\u4e0d\u7b26\u5408']),
      pickFirst(row, ['other', 'Other', '\u5176\u5b83', '\u5176\u4ed6']),
      pickFirst(row, ['reason', 'Reason', '\u539f\u56e0', 'note', 'description'])
    );
  });

  const hasData = Object.values(bucket).some((entry) => entry && (entry.value || entry.note));
  if (!rows.length || !hasData) {
    const lines = textOf(feedbackText).split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
    FIELD_ORDER.forEach((fieldKey) => {
      const related = lines.filter((line) => FIELD_META[fieldKey].keywords.some((keyword) => line.includes(keyword)));
      if (!related.length || bucket[fieldKey]) return;
      let value = '';
      if (fieldKey === 'name') value = extractNameValue(...related) || textOf(context.applicantName);
      if (fieldKey === 'course') value = extractCourseValues(...related).join('\n');
      if (fieldKey === 'period') value = extractGenericValue('period', ...related);
      if (fieldKey === 'exam') value = extractGenericValue('exam', ...related);
      if (fieldKey === 'target') value = extractGenericValue('target', ...related);
      const failedLine = related.find((line) => line.includes('\u4e0d\u7b26\u5408') || line.includes('\u4e0d\u4e00\u81f4') || line.includes('\u672a\u901a\u904e'));
      bucket[fieldKey] = {
        value,
        status: value ? (failedLine ? 'fail' : 'pass') : 'other',
        note: failedLine || '\u672a\u6293\u53d6\u5230\u9019\u500b\u9805\u76ee',
      };
    });
  }

  return (() => {
    const output = [];

    FIELD_ORDER.forEach((fieldKey) => {
      const entry = bucket[fieldKey];
      const label = FIELD_META[fieldKey].label;

      if (!entry) {
        output.push({
          [COL_ITEM]: `${label}：${DISPLAY_MISSING_TEXT}`,
          [COL_PASS]: '-',
          [COL_FAIL]: DISPLAY_MISSING_TEXT,
          [COL_OTHER]: '-',
          [COL_LLM]: '',
          [COL_REASON]: '',
        });
        return;
      }

      if (fieldKey === 'course') {
        const courses = (entry.value || '')
          .split('\n')
          .map((v) => v.trim())
          .filter(Boolean);

        if (courses.length) {
          courses.forEach((course, index) => {
            output.push({
              [COL_ITEM]: `課程${index + 1}：${course}`,
              [COL_PASS]: entry.status === 'pass' ? '○' : '-',
              [COL_FAIL]: entry.status === 'fail' ? (entry.note || DISPLAY_MISSING_TEXT) : '-',
              [COL_OTHER]: '-',
              [COL_LLM]: '',
              [COL_REASON]: '',
            });
          });
        } else {
          output.push({
            [COL_ITEM]: `課程1：${DISPLAY_MISSING_TEXT}`,
            [COL_PASS]: '-',
            [COL_FAIL]: entry.status === 'fail' ? (entry.note || DISPLAY_MISSING_TEXT) : DISPLAY_MISSING_TEXT,
            [COL_OTHER]: '-',
            [COL_LLM]: '',
            [COL_REASON]: '',
          });
        }
        return;
      }

      const itemText = entry.value ? `${label}：${entry.value}` : `${label}：${DISPLAY_MISSING_TEXT}`;

      output.push({
        [COL_ITEM]: itemText,
        [COL_PASS]: entry.status === 'pass' ? '○' : '-',
        [COL_FAIL]: entry.status === 'fail' ? (entry.note || DISPLAY_MISSING_TEXT) : '-',
        [COL_OTHER]: '-',
        [COL_LLM]: '',
        [COL_REASON]: '',
      });
    });

    return output;
  })();
}

function getQuery() {
  const q = new URLSearchParams(location.search);
  return {
    applicantStdn: (q.get('applicantStdn') || '').trim(),
    applicantNo: (q.get('applicantNo') || '').trim(),
    source: (q.get('source') || 'unlabeled').trim(),
  };
}

function backToList(source) {
  location.href = `label.html?tab=${encodeURIComponent(source || 'unlabeled')}`;
}

function renderFeedbackTable(rows, titleText, feedbackText, context = {}) {
  const normalizedRows = normalizeFeedbackRows(rows, feedbackText, context);
  if (!Array.isArray(normalizedRows) || normalizedRows.length === 0) return null;
  const headers = [COL_ITEM, COL_PASS, COL_FAIL, COL_OTHER];
  const wrap = el('div', 'table-wrap');
  if (titleText) wrap.appendChild(el('div', 'review-label', titleText));
  const table = document.createElement('table');
  table.className = 'ai-feedback-table compact';
  const thead = document.createElement('thead');
  const trh = document.createElement('tr');
  headers.forEach((h) => {
    const th = document.createElement('th');
    th.textContent = h;
    trh.appendChild(th);
  });
  thead.appendChild(trh);
  const tbody = document.createElement('tbody');
  normalizedRows.forEach((row) => {
    const tr = document.createElement('tr');
    headers.forEach((h) => {
      const td = document.createElement('td');
      td.textContent = row?.[h] ?? '-';
      if (h === COL_ITEM) td.style.whiteSpace = 'pre-wrap';
      if (h === COL_PASS && row?.[h] === '\u25cb') td.classList.add('mark');
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(thead);
  table.appendChild(tbody);
  wrap.appendChild(table);
  return wrap;
}

function normalizeEditableRows(rows) {
  if (!Array.isArray(rows)) return [];
  return rows.map((row) => {
    const pass = String(row?.[COL_PASS] || '').trim();
    const fail = String(row?.[COL_FAIL] || '').trim();
    const status = pass && pass !== '\u5426' ? 'pass' : fail && fail !== '\u5426' ? 'fail' : 'pass';
    return {
      item: row?.[COL_ITEM] ?? '',
      result: row?.[COL_LLM] ?? '',
      status,
      reason: row?.[COL_REASON] ?? '',
    };
  });
}

function buildEditableTable(rows, locked) {
  const headers = [COL_ITEM, COL_PASS, COL_FAIL, COL_OTHER, 'Action'];
  const wrap = el('div', 'table-wrap');
  wrap.appendChild(el('div', 'review-label', 'Teacher Edit Table'));

  const table = document.createElement('table');
  table.className = 'ai-feedback-table';
  const thead = document.createElement('thead');
  const trh = document.createElement('tr');
  headers.forEach((h) => {
    const th = document.createElement('th');
    th.textContent = h;
    trh.appendChild(th);
  });
  thead.appendChild(trh);
  const tbody = document.createElement('tbody');

  function addRow(data = {}) {
    const tr = document.createElement('tr');
    tr.dataset.row = '1';

    const tdItem = document.createElement('td');
    const inputItem = document.createElement('input');
    inputItem.type = 'text';
    inputItem.value = data.item || '';
    inputItem.disabled = locked;
    inputItem.dataset.field = 'item';
    tdItem.appendChild(inputItem);

    const inputResult = document.createElement('input');
    inputResult.type = 'hidden';
    inputResult.value = data.result || '';
    inputResult.dataset.field = 'result';
    tdItem.appendChild(inputResult);

    const tdPass = document.createElement('td');
    const passRadio = document.createElement('input');
    passRadio.type = 'radio';
    passRadio.name = `status_${Date.now()}_${Math.random().toString(16).slice(2)}`;
    passRadio.value = 'pass';
    passRadio.checked = (data.status || 'pass') === 'pass';
    passRadio.disabled = locked;
    passRadio.dataset.field = 'pass';
    tdPass.appendChild(passRadio);

    const tdFail = document.createElement('td');
    const failRadio = document.createElement('input');
    failRadio.type = 'radio';
    failRadio.name = passRadio.name;
    failRadio.value = 'fail';
    failRadio.checked = (data.status || 'pass') === 'fail';
    failRadio.disabled = locked;
    failRadio.dataset.field = 'fail';
    tdFail.appendChild(failRadio);

    const tdOther = document.createElement('td');
    const inputOther = document.createElement('input');
    inputOther.type = 'text';
    inputOther.value = data.reason || '';
    inputOther.disabled = locked;
    inputOther.dataset.field = 'reason';
    tdOther.appendChild(inputOther);

    const tdAction = document.createElement('td');
    if (!locked) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'btn ghost sm';
      btn.textContent = 'Remove';
      btn.addEventListener('click', () => {
        tr.remove();
      });
      tdAction.appendChild(btn);
    } else {
      tdAction.textContent = '-';
    }

    tr.appendChild(tdItem);
    tr.appendChild(tdPass);
    tr.appendChild(tdFail);
    tr.appendChild(tdOther);
    tr.appendChild(tdAction);
    tbody.appendChild(tr);
  }

  const list = normalizeEditableRows(normalizeFeedbackRows(rows));
  if (list.length === 0) {
    addRow();
  } else {
    list.forEach(addRow);
  }

  table.appendChild(thead);
  table.appendChild(tbody);
  wrap.appendChild(table);

  if (!locked) {
    const actions = el('div', 'table-actions');
    const addBtn = el('button', 'btn ghost', 'Add Row');
    addBtn.type = 'button';
    addBtn.addEventListener('click', () => addRow());
    actions.appendChild(addBtn);
    wrap.appendChild(actions);
  }

  wrap.getRows = () => {
    return [...tbody.querySelectorAll('tr[data-row]')].map((tr) => {
      const itemInput = tr.querySelector('input[data-field="item"]');
      const resultInput = tr.querySelector('input[data-field="result"]');
      const passChecked = tr.querySelector('input[data-field="pass"]')?.checked;
      const failChecked = tr.querySelector('input[data-field="fail"]')?.checked;
      const reasonInput = tr.querySelector('input[data-field="reason"]');
      const item = itemInput?.value?.trim() || '';
      const result = resultInput?.value?.trim() || '';
      const status = failChecked ? 'fail' : 'pass';
      const reason = reasonInput?.value?.trim() || '';
      return { item, result, status, reason };
    }).filter((row) => row.item || row.result || row.reason);
  };

  return wrap;
}

function clamp01(v) {
  if (Number.isNaN(v)) return 0;
  return Math.min(1, Math.max(0, v));
}

function createRegionEditor(overlayEl, countEl) {
  const state = {
    drawEnabled: true,
    isDrawing: false,
    startX: 0,
    startY: 0,
    activeBox: null,
    regions: [],
    pointerId: null,
  };
  let scrollProvider = null;

  function getScrollState() {
    if (!scrollProvider) return null;
    try {
      return scrollProvider();
    } catch (err) {
      return null;
    }
  }

  function updateCount() {
    if (countEl) countEl.textContent = `Regions: ${state.regions.length}`;
  }

  function renderRegions() {
    const scrollState = getScrollState();
    overlayEl.querySelectorAll('.selection-box').forEach((n) => n.remove());
    state.regions.forEach((r) => {
      let left = r.x;
      let top = r.y;
      let width = r.width;
      let height = r.height;
      if (scrollState && r.space === 'scroll') {
        const baseW = scrollState.clientWidth || 1;
        const baseH = scrollState.clientHeight || 1;
        left = r.x - (scrollState.scrollLeft - (r.scrollLeft || 0)) / baseW;
        top = r.y - (scrollState.scrollTop - (r.scrollTop || 0)) / baseH;
      }
      const node = document.createElement('div');
      node.className = 'selection-box';
      node.style.left = `${left * 100}%`;
      node.style.top = `${top * 100}%`;
      node.style.width = `${width * 100}%`;
      node.style.height = `${height * 100}%`;
      overlayEl.appendChild(node);
    });
    updateCount();
  }

  function finishDrawing() {
    if (!state.activeBox) return;
    const rect = overlayEl.getBoundingClientRect();
    const boxRect = state.activeBox.getBoundingClientRect();
    const x = clamp01((boxRect.left - rect.left) / rect.width);
    const y = clamp01((boxRect.top - rect.top) / rect.height);
    const width = clamp01(boxRect.width / rect.width);
    const height = clamp01(boxRect.height / rect.height);
    const scrollState = getScrollState();
    state.activeBox.remove();
    state.activeBox = null;
    if (width < 0.01 || height < 0.01) {
      renderRegions();
      return;
    }
    if (scrollState) {
      state.regions.push({
        x: Number(x.toFixed(6)),
        y: Number(y.toFixed(6)),
        width: Number(width.toFixed(6)),
        height: Number(height.toFixed(6)),
        scrollTop: Number((scrollState.scrollTop || 0).toFixed(2)),
        scrollLeft: Number((scrollState.scrollLeft || 0).toFixed(2)),
        space: 'scroll',
      });
    } else {
      state.regions.push({
        x: Number(x.toFixed(6)),
        y: Number(y.toFixed(6)),
        width: Number(width.toFixed(6)),
        height: Number(height.toFixed(6)),
      });
    }
    renderRegions();
  }

  overlayEl.addEventListener('pointerdown', (e) => {
    if (!state.drawEnabled) return;
    if (e.button !== 0) return;
    e.preventDefault();
    try {
      overlayEl.setPointerCapture(e.pointerId);
    } catch (err) {}
    state.pointerId = e.pointerId;
    const rect = overlayEl.getBoundingClientRect();
    state.isDrawing = true;
    state.startX = e.clientX - rect.left;
    state.startY = e.clientY - rect.top;
    const node = document.createElement('div');
    node.className = 'selection-box active';
    node.style.left = `${state.startX}px`;
    node.style.top = `${state.startY}px`;
    node.style.width = '0px';
    node.style.height = '0px';
    overlayEl.appendChild(node);
    state.activeBox = node;
  });

  overlayEl.addEventListener('pointermove', (e) => {
    if (!state.isDrawing || !state.activeBox) return;
    if (state.pointerId !== null && e.pointerId !== state.pointerId) return;
    e.preventDefault();
    const rect = overlayEl.getBoundingClientRect();
    const curX = Math.min(Math.max(e.clientX - rect.left, 0), rect.width);
    const curY = Math.min(Math.max(e.clientY - rect.top, 0), rect.height);
    const left = Math.min(state.startX, curX);
    const top = Math.min(state.startY, curY);
    const width = Math.abs(curX - state.startX);
    const height = Math.abs(curY - state.startY);
    state.activeBox.style.left = `${left}px`;
    state.activeBox.style.top = `${top}px`;
    state.activeBox.style.width = `${width}px`;
    state.activeBox.style.height = `${height}px`;
  });

  const finishHandler = (e) => {
    if (!state.isDrawing) return;
    if (state.pointerId !== null && e && e.pointerId !== state.pointerId) return;
    state.isDrawing = false;
    if (state.pointerId !== null && e) {
      try {
        overlayEl.releasePointerCapture(e.pointerId);
      } catch (err) {}
    }
    state.pointerId = null;
    finishDrawing();
  };
  overlayEl.addEventListener('pointerup', finishHandler);
  overlayEl.addEventListener('pointercancel', finishHandler);
  overlayEl.addEventListener('lostpointercapture', finishHandler);
  overlayEl.addEventListener('wheel', (e) => {
    if (!state.drawEnabled) return;
    e.preventDefault();
  }, { passive: false });

  return {
    setDrawEnabled(enabled) {
      state.drawEnabled = !!enabled;
      overlayEl.classList.toggle('draw-enabled', state.drawEnabled);
      overlayEl.classList.toggle('draw-disabled', !state.drawEnabled);
    },
    setScrollProvider(provider) {
      scrollProvider = typeof provider === 'function' ? provider : null;
      renderRegions();
    },
    refresh() {
      renderRegions();
    },
    undoLast() {
      if (state.regions.length > 0) {
        state.regions.pop();
        renderRegions();
      }
    },
    clearAll() {
      state.regions = [];
      renderRegions();
    },
    getRegions() {
      return state.regions.map((r) => ({
        x: r.x,
        y: r.y,
        width: r.width,
        height: r.height,
      }));
    },
  };
}

function renderDetail(host, rec, source) {
  host.innerHTML = '';
  const locked = !!rec.label;

  const header = el('div', 'fbx-hd');
  const pill = el('span', `pill ${rec.isPassed ? 'ok' : 'ng'}`, rec.isPassed ? 'AI PASS' : 'AI FAIL');
  const title = el('div', 'review-label', 'AI Result');
  header.appendChild(pill);
  header.appendChild(title);

  const feedbackTable = renderFeedbackTable(
    rec.aiFeedbackTable,
    'AI Table',
    rec.aiFeedback || '',
    { applicantName: rec.applicantName || '' }
  );

  const pdfWrap = el('div', 'pdf-wrap');
  const pdfTitle = el('div', 'review-label', 'PDF Preview');
  const toolRow = el('div', 'pdf-tool-row');
  const btnToggleDraw = el('button', 'btn ghost', 'Marking: Off');
  btnToggleDraw.type = 'button';
  const btnUndo = el('button', 'btn ghost', 'Undo');
  btnUndo.type = 'button';
  const btnClear = el('button', 'btn ghost', 'Clear');
  btnClear.type = 'button';
  const boxCount = el('span', 'muted', 'Regions: 0');
  toolRow.appendChild(btnToggleDraw);
  toolRow.appendChild(btnUndo);
  toolRow.appendChild(btnClear);
  toolRow.appendChild(boxCount);

  const stage = el('div', 'pdf-stage');
  const pdf = el('div', 'pdf-viewer');
  const canvasWrap = el('div', 'pdf-canvas-wrap');
  const overlay = el('div', 'pdf-overlay');
  canvasWrap.appendChild(overlay);
  pdf.appendChild(canvasWrap);
  stage.appendChild(pdf);
  pdfWrap.appendChild(pdfTitle);
  pdfWrap.appendChild(toolRow);
  pdfWrap.appendChild(stage);

  const editor = createRegionEditor(overlay, boxCount);
  let drawEnabled = false;
  const applyDrawState = (enabled) => {
    editor.setDrawEnabled(enabled);
    pdf.classList.toggle('marking-disabled', enabled);
  };
  applyDrawState(drawEnabled);
  let pdfDoc = null;
  let renderSeq = 0;

  function ensurePdfJs() {
    if (window.pdfjsLib) return window.pdfjsLib;
    return null;
  }

  async function renderPdfDocument() {
    if (!rec.pdf_path) return;
    const pdfjsLib = ensurePdfJs();
    if (!pdfjsLib) {
      canvasWrap.textContent = 'PDF.js not loaded.';
      return;
    }
    if (!pdfjsLib.GlobalWorkerOptions.workerSrc) {
      pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.js';
    }
    const url = `${API_BASE}/${String(rec.pdf_path).replace(/^\//, '')}`;
    try {
      const loadingTask = pdfjsLib.getDocument({ url, withCredentials: true });
      pdfDoc = await loadingTask.promise;
      await renderAllPages();
      editor.refresh();
    } catch (err) {
      canvasWrap.textContent = err?.message || 'PDF load failed.';
    }
  }

  async function renderAllPages() {
    if (!pdfDoc) return;
    const seq = ++renderSeq;
    while (canvasWrap.firstChild) {
      canvasWrap.removeChild(canvasWrap.firstChild);
    }
    canvasWrap.appendChild(overlay);
    const firstPage = await pdfDoc.getPage(1);
    const unscaled = firstPage.getViewport({ scale: 1 });
    const containerWidth = Math.max(1, pdf.clientWidth - 2);
    const scale = Math.max(0.1, Math.min(4, containerWidth / unscaled.width));
    const outputScale = window.devicePixelRatio || 1;
    let maxWidth = 0;
    for (let i = 1; i <= pdfDoc.numPages; i += 1) {
      if (seq !== renderSeq) return;
      const page = await pdfDoc.getPage(i);
      const viewport = page.getViewport({ scale });
      const canvas = document.createElement('canvas');
      canvas.className = 'pdf-page-canvas';
      const ctx = canvas.getContext('2d');
      canvas.width = Math.floor(viewport.width * outputScale);
      canvas.height = Math.floor(viewport.height * outputScale);
      canvas.style.width = `${viewport.width}px`;
      canvas.style.height = `${viewport.height}px`;
      ctx.setTransform(outputScale, 0, 0, outputScale, 0, 0);
      await page.render({ canvasContext: ctx, viewport }).promise;
      canvasWrap.insertBefore(canvas, overlay);
      maxWidth = Math.max(maxWidth, viewport.width);
    }
    canvasWrap.style.width = `${maxWidth}px`;
  }

  const debouncedResize = (() => {
    let t = null;
    return () => {
      if (!pdfDoc) return;
      if (t) clearTimeout(t);
      t = setTimeout(() => {
        renderAllPages();
      }, 200);
    };
  })();
  window.addEventListener('resize', debouncedResize);

  renderPdfDocument();
  btnToggleDraw.addEventListener('click', () => {
    drawEnabled = !drawEnabled;
    applyDrawState(drawEnabled);
    btnToggleDraw.textContent = drawEnabled ? 'Marking: On' : 'Marking: Off';
  });
  btnUndo.addEventListener('click', () => editor.undoLast());
  btnClear.addEventListener('click', () => editor.clearAll());

  const editableTable = buildEditableTable(
    (rec.label && rec.label.correctedFeedbackTable?.length ? rec.label.correctedFeedbackTable : rec.aiFeedbackTable) || [],
    locked
  );

  const form = el('form', 'label-form');
  form.innerHTML = `
    <div class="actions">
      <button class="btn ghost" type="button" id="btnCancelLabel">Back</button>
      <button class="btn primary" type="submit">Save</button>
    </div>
  `;

  if (locked && rec.label) {
    form.querySelectorAll('button').forEach((node) => {
      if (node.id === 'btnCancelLabel') return;
      node.disabled = true;
    });
    const lockNote = el('div', 'muted', 'This record is submitted and locked.');
    form.insertBefore(lockNote, form.firstChild);
  }

  const btnCancel = form.querySelector('#btnCancelLabel');
  if (btnCancel) {
    btnCancel.addEventListener('click', () => {
      backToList(source);
    });
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const rows = editableTable.getRows();
    const hasRows = rows.length > 0;
    const allPass = hasRows && rows.every((row) => row.status === 'pass');
    const anyFail = rows.some((row) => row.status === 'fail');
    const correctedIsPassed = allPass ? true : anyFail ? false : null;
    const reviewStatus = correctedIsPassed === true ? 'approved' : correctedIsPassed === false ? 'rejected' : 'returned';
    const correctedFeedbackTable = rows.map((row) => ({
      [COL_ITEM]: row.item,
      [COL_LLM]: row.result,
      [COL_PASS]: row.status === 'pass' ? '\u662f' : '\u5426',
      [COL_FAIL]: row.status === 'fail' ? '\u662f' : '\u5426',
      [COL_REASON]: row.reason,
    }));

    const payload = {
      applicantStdn: rec.applicantStdn,
      applicantNo: rec.applicantNo,
      reviewStatus,
      correctedIsPassed,
      correctedFeedback: '',
      correctedFeedbackTable,
      reviewer: '',
      reviewComment: '',
      selectedRegions: editor.getRegions(),
    };
    try {
      const res = await fetch(`${API_BASE}/api/labeling/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      alert('Submitted.');
      backToList('labeled');
    } catch (err) {
      alert(err.message || 'Submit failed.');
    }
  });

  host.appendChild(header);
  if (feedbackTable) host.appendChild(feedbackTable);
  host.appendChild(pdfWrap);
  host.appendChild(editableTable);
  host.appendChild(form);
}

async function initPage() {
  const host = document.getElementById('labelDetailHost');
  const backBtn = document.getElementById('btnBackToList');
  const { applicantStdn, applicantNo, source } = getQuery();

  if (backBtn) {
    backBtn.addEventListener('click', () => backToList(source));
  }

  if (!host) return;
  if (!applicantStdn || !applicantNo) {
    host.textContent = 'Missing applicantStdn or applicantNo';
    return;
  }

  try {
    const url = `${API_BASE}/api/labeling/record?applicantStdn=${encodeURIComponent(applicantStdn)}&applicantNo=${encodeURIComponent(applicantNo)}`;
    const res = await fetch(url, { credentials: 'include' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    renderDetail(host, data, source);
  } catch (err) {
    host.textContent = err.message || 'Load failed.';
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initPage);
} else {
  initPage();
}
