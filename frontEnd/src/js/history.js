function resolveApiBase() {
  try {
    const meta = document.querySelector('meta[name="api-base"]');
    if (meta?.content) {
      const url = new URL(meta.content);
      const host = location.hostname;
      if (host && url.hostname && url.hostname !== host) {
        url.hostname = host;
      }
      return url.origin.replace(/\/+$/, '');
    }
  } catch (error) {}
  return "";
}

const API_BASE = resolveApiBase();

function getStoredUser() {
  try {
    return JSON.parse(localStorage.getItem('user') || '{}');
  } catch (e) {
    return {};
  }
}

function isTeacherRole() {
  const role = (getStoredUser().role || '').trim();
  return role && role !== 'applicant';
}

const COL_ITEM = '\u9805\u76ee';
const COL_PASS = '\u7b26\u5408';
const COL_FAIL = '\u4e0d\u7b26\u5408';
const COL_OTHER = '\u5176\u5b83';

const FIELD_ORDER = ['name', 'course', 'period', 'exam', 'target'];
const FIELD_META = {
  name: { label: '\u4e2d\u6587\u59d3\u540d', keywords: ['\u4e2d\u6587\u59d3\u540d', '\u7533\u8acb\u4eba\u59d3\u540d', '\u8b49\u66f8\u59d3\u540d', '\u59d3\u540d'] },
  course: { label: '\u8ab2\u7a0b\u540d\u7a31', keywords: ['\u8ab2\u7a0b\u540d\u7a31', '\u8ab2\u7a0b'] },
  period: { label: '\u8ab2\u7a0b\u671f\u9593', keywords: ['\u8ab2\u7a0b\u671f\u9593', '\u958b\u8ab2\u671f\u9593'] },
  exam: { label: '\u6709\u7121\u6e2c\u9a57', keywords: ['\u6709\u7121\u6e2c\u9a57', '\u6e2c\u9a57', '\u6e2c\u9a57\u6210\u7e3e'] },
  target: { label: '\u9069\u7528\u5c0d\u8c61', keywords: ['\u9069\u7528\u5c0d\u8c61'] },
};

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

function cleanCourseLine(line) {
  let value = textOf(line);
  if (!value) return '';
  value = value.replace(/^[^:：]*[:：]\s*/, '');
  value = value.replace(/\s*[|｜]\s*(\u8a8d\u8b49\u6642\u6578|\u6e2c\u9a57\u6210\u7e3e|\u9069\u7528\u5c0d\u8c61|\u7e3d\u6642\u6578).*/, '');
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

function expandPackedRows(rawRows) {
  const rows = Array.isArray(rawRows) ? rawRows : [];
  const expanded = [];
  const expectedItems = ['中文姓名', '課程名稱', '課程期間', '有無測驗', '適用對象'];

  rows.forEach((row) => {
    const itemText = pickFirst(row, ['item', 'Item', '項目', '辨識項目']);
    const resultText = pickFirst(row, ['result', 'Result', 'LLM Result', 'LLM辨識到結果', '辨識結果']);
    const passText = pickFirst(row, ['pass', 'Pass', '符合', 'isPass', 'isPassed']) || '-';
    const failText = pickFirst(row, ['fail', 'Fail', '不符合']) || '-';
    const otherText = pickFirst(row, ['other', 'Other', '其它', '其他']) || '-';

    const itemParts = itemText.split(/[|｜]/).map((part) => part.trim()).filter(Boolean);
    const resultParts = resultText.split(/[|｜]/).map((part) => part.trim());
    if (itemParts.length === expectedItems.length && expectedItems.every((item, index) => itemParts[index] === item)) {
      expectedItems.forEach((item, index) => {
        const value = resultParts[index] || '';
        expanded.push({
          item,
          result: value === '未抓取到這個項目' ? '' : value,
          pass: value && value !== '未抓取到這個項目' ? passText : '-',
          fail: failText,
          other: value && value !== '未抓取到這個項目' ? '-' : otherText,
        });
      });
      return;
    }

    expanded.push(row);
  });

  return expanded;
}

function splitLines(value) {
  return textOf(value)
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line && !isMissingItem(line));
}

function isMissingItem(value) {
  const text = textOf(value);
  return text === '未抓取到這個項目'
    || text === '未擷取到這個項目'
    || text === '未檢測到這個項目'
    || /未(?:抓取|擷取|檢測)到這個項目/.test(text);
}

function hasMissingItemText(value) {
  return /未(?:抓取|擷取|檢測)到這個項目/.test(textOf(value));
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
    : (existing.note && existing.note !== '未抓取到這個項目' ? existing.note : incoming.note);

  return {
    value: mergedValue,
    status,
    note: note || '未抓取到這個項目',
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
        ? '未抓取到這個項目'
        : (failed ? (failText && !isMarked(failText) ? failText : reasonText) : (otherText || '未抓取到這個項目')),
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

  return FIELD_ORDER.map((fieldKey) => {
    const entry = bucket[fieldKey];
    if (!entry) {
      return {
        [COL_ITEM]: FIELD_META[fieldKey].label,
        [COL_PASS]: '-',
        [COL_FAIL]: '-',
        [COL_OTHER]: '\u672a\u6293\u53d6\u5230\u9019\u500b\u9805\u76ee',
      };
    }

    let itemText = FIELD_META[fieldKey].label;
    if (entry.value) {
      if (fieldKey === 'course') {
        const courseLines = entry.value
          .split('\n')
          .map((value) => value.trim())
          .filter(Boolean)
          .map((value, index) => `\u8ab2\u7a0b${index + 1}\uff1a${value}`);
        itemText = `${FIELD_META[fieldKey].label}\n${courseLines.join('\n')}`;
      } else {
        itemText = `${FIELD_META[fieldKey].label}\uff1a${entry.value}`;
      }
    }

    return {
      [COL_ITEM]: itemText,
      [COL_PASS]: entry.status === 'pass' ? '\u25cb' : '-',
      [COL_FAIL]: entry.status === 'fail'
        ? (isMissingItem(entry.note) ? '\u4e0d\u7b26\u5408' : (entry.note || '\u4e0d\u7b26\u5408'))
        : '-',
      [COL_OTHER]: entry.value ? '-' : (entry.note || '\u672a\u6293\u53d6\u5230\u9019\u500b\u9805\u76ee'),
    };
  });
}

function renderFeedbackTable(rows, feedbackText, context = {}) {
  const data = normalizeFeedbackRows(rows, feedbackText, context);
  const headers = [COL_ITEM, COL_PASS, COL_FAIL, COL_OTHER];
  const table = document.createElement('table');
  table.className = 'ai-feedback-table compact';

  const thead = document.createElement('thead');
  const trh = document.createElement('tr');
  headers.forEach((header) => {
    const th = document.createElement('th');
    th.textContent = header;
    trh.appendChild(th);
  });
  thead.appendChild(trh);

  const tbody = document.createElement('tbody');
  data.forEach((row) => {
    const tr = document.createElement('tr');
    headers.forEach((header) => {
      const td = document.createElement('td');
      const value = row?.[header] || '-';
      td.textContent = value;
      if (header === COL_ITEM) td.style.whiteSpace = 'pre-wrap';
      if (header === COL_PASS && value === '\u25cb') td.classList.add('mark');
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });

  table.appendChild(thead);
  table.appendChild(tbody);
  return table;
}

function getFilterValues() {
  const time = document.getElementById('recordTime')?.value || '';
  const studentId = document.getElementById('recordStudentId')?.value || '';
  const name = document.getElementById('recordName')?.value || '';

  const filters = {};
  if (time) filters.time = time.trim();
  if (studentId) filters.student_id = studentId.trim();
  if (name) filters.name = name.trim();
  return filters;
}

window.getHistoryFilters = getFilterValues;

(function initRecordQuery() {
  const form = document.getElementById('recordQueryForm');
  const listEl = document.getElementById('recordList');
  if (!form || !listEl) return;
  let teacherAccess = false;

  function renderEmpty(message, colSpan) {
    listEl.innerHTML = '';
    const tr = document.createElement('tr');
    const td = document.createElement('td');
    td.colSpan = colSpan;
    td.className = 'empty';
    td.textContent = message;
    tr.appendChild(td);
    listEl.appendChild(tr);
  }

  async function fetchRecords(filters) {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => params.set(key, value));
    const url = `${API_BASE}/api/history/search?${params.toString()}`;
    const response = await fetch(url, { method: 'GET', credentials: 'include' });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    return data;
  }

  async function checkTeacherAccess() {
    if (!isTeacherRole()) return false;
    try {
      const res = await fetch(`${API_BASE}/api/labeling/unlabeled?limit=1&offset=0`, { credentials: 'include' });
      if (!res.ok) return false;
      return true;
    } catch (e) {
      return false;
    }
  }

  function renderRows(records) {
    listEl.innerHTML = '';
    records.forEach((record) => {
      const tr = document.createElement('tr');
      tr.className = 'row-main';

      const tdTime = document.createElement('td');
      tdTime.textContent = `${record.applyDate || ''} ${record.applyTime || ''}`.trim() || '-';

      const tdSid = document.createElement('td');
      tdSid.textContent = record.applicantStdn || '-';

      const tdName = document.createElement('td');
      tdName.textContent = record.applicantName || '-';

      const tdAction = document.createElement('td');
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'btn ghost sm';
      btn.textContent = 'View';
      tdAction.appendChild(btn);

      tr.appendChild(tdTime);
      tr.appendChild(tdSid);
      tr.appendChild(tdName);
      tr.appendChild(tdAction);

      const details = document.createElement('tr');
      details.className = 'row-details is-hidden';
      const detailCell = document.createElement('td');
      detailCell.colSpan = 4;
      detailCell.className = 'detail-cell';

      const feedbackText = record.finalFeedback || record.aiFeedback || 'No feedback yet.';
      const tableRows = Array.isArray(record.finalFeedbackTable) && record.finalFeedbackTable.length ? record.finalFeedbackTable : record.aiFeedbackTable;

      const summary = document.createElement('div');
      summary.className = 'fbx-summary';
      summary.textContent = feedbackText;
      detailCell.appendChild(summary);

      if (teacherAccess && record.applicantStdn && record.applicantNo !== undefined && record.applicantNo !== null) {
        const actions = document.createElement('div');
        actions.className = 'detail-actions';
        const editBtn = document.createElement('button');
        editBtn.type = 'button';
        editBtn.className = 'btn ghost sm';
        editBtn.textContent = 'Edit';
        editBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          const qs = new URLSearchParams({
            applicantStdn: String(record.applicantStdn),
            applicantNo: String(record.applicantNo),
            source: 'history',
          });
          location.href = `label_detail.html?${qs.toString()}`;
        });
        actions.appendChild(editBtn);
        detailCell.appendChild(actions);
      }

      const divider = document.createElement('div');
      divider.className = 'divider';
      detailCell.appendChild(divider);
      detailCell.appendChild(renderFeedbackTable(tableRows, feedbackText, { applicantName: record.applicantName || '' }));

      details.appendChild(detailCell);

      btn.addEventListener('click', (event) => {
        event.stopPropagation();
        details.classList.toggle('is-hidden');
        btn.textContent = details.classList.contains('is-hidden') ? 'View' : 'Hide';
      });

      listEl.appendChild(tr);
      listEl.appendChild(details);
    });
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    renderEmpty('Loading...', 4);
    try {
      teacherAccess = await checkTeacherAccess();
      const data = await fetchRecords(getFilterValues());
      if (!data.records?.length) {
        renderEmpty('No data found.', 4);
        return;
      }
      renderRows(data.records);
    } catch (error) {
      renderEmpty(error.message || 'Query failed.', 4);
    }
  });

  async function initialLoad() {
    renderEmpty('Loading...', 4);
    try {
      teacherAccess = await checkTeacherAccess();
      const data = await fetchRecords({});
      if (!data.records?.length) {
        renderEmpty('No data found.', 4);
        return;
      }
      renderRows(data.records);
    } catch (error) {
      renderEmpty(error.message || 'Query failed.', 4);
    }
  }

  initialLoad();
})();
