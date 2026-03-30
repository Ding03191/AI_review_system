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

function is??Role() {
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

const MISSING_ITEM_TEXT = '????????';
const DISPLAY_MISSING_TEXT = '???';

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

function extract??Value(...parts) {
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
  const expectedItems = ['', '', '', '', ''];

  rows.forEach((row) => {
    const itemText = pickFirst(row, ['item', 'Item', '', '']);
      pickFirst(row, ['result', '辨識結果', 'LLM 辨識結果', 'LLM辨識結果', '辨識結果']),
    const passText = pickFirst(row, ['pass', 'Pass', '', 'isPass', 'isPassed']) || '-';
    const failText = pickFirst(row, ['fail', 'Fail', '不符合']) || '-';
    const otherText = pickFirst(row, ['other', 'Other', '', '']) || '-';

    const itemParts = itemText.split(/[|]/).map((part) => part.trim()).filter(Boolean);
    const resultParts = resultText.split(/[|]/).map((part) => part.trim());
    if (itemParts.length === expectedItems.length && expectedItems.every((item, index) => itemParts[index] === item)) {
      expectedItems.forEach((item, index) => {
        const value = resultParts[index] || '';
        expanded.push({
          item,
          result: value === MISSING_ITEM_TEXT ? '' : value,
          pass: value && value !== MISSING_ITEM_TEXT ? passText : '-',
          fail: failText,
          other: value && value !== MISSING_ITEM_TEXT ? '-' : otherText,
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
  return text === MISSING_ITEM_TEXT
    || text === DISPLAY_MISSING_TEXT
    || /(未抓取|未擷取|未檢測).*?項目/.test(text)
    || /未找到/.test(text);
}

function hasMissingItemText(value) {
  return /(未抓取|未擷取|未檢測).*?項目/.test(textOf(value)) || /未找到/.test(textOf(value));
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
  if (fieldKey === 'name') return extract??Value(resultText, itemText) || textOf(resultText) || textOf(context.applicant??);
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

function build??Bucket(rawRows, feedbackText, context = {}) {
  const rows = expandPackedRows(rawRows);
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
        ? DISPLAY_MISSING_TEXT
        : (failed ? (failText && !isMarked(failText) ? failText : reasonText) : (otherText || DISPLAY_MISSING_TEXT)),
    };
    bucket[fieldKey] = mergeEntry(bucket[fieldKey], entry, fieldKey);
  };

  rows.forEach((row) => {
    ingest(
      pickFirst(row, ['item', 'Item', '\u9805\u76ee', '\u8fa8\u8b58\u9805\u76ee']),
      pickFirst(row, ['result', '辨識結果', 'LLM 辨識結果', 'LLM辨識結果', '辨識結果']),
      pickFirst(row, ['pass', 'Pass', '\u7b26\u5408', 'isPass', 'isPassed']),
      pickFirst(row, ['fail', 'Fail', '\u4e0d\u7b26\u5408']),
      pickFirst(row, ['other', 'Other', '\u5176\u5b83', '\u5176\u4ed6']),
      pickFirst(row, ['reason', 'Reason', '\u539f\u56e0', 'note', 'description'])
    );
  });

  if (!rows.length) {
    const lines = textOf(feedbackText).split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
    FIELD_ORDER.forEach((fieldKey) => {
      const related = lines.filter((line) => FIELD_META[fieldKey].keywords.some((keyword) => line.includes(keyword)));
      if (!related.length || bucket[fieldKey]) return;
      let value = '';
      if (fieldKey === 'name') value = extract??Value(...related) || textOf(context.applicant??);
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

  return bucket;
}

function getCourseListFromBucket(bucket) {
  const base = splitLines(bucket?.course?.value || '');
  if (base.some((line) => /--- Page \d+ ---/.test(line))) {
    const groups = [];
    let buffer = [];
    base.forEach((line) => {
      if (/--- Page \d+ ---/.test(line)) {
        if (buffer.length) {
          groups.push(buffer.join('\n'));
          buffer = [];
        }
        return;
      }
      buffer.push(line);
    });
    if (buffer.length) groups.push(buffer.join('\n'));
    return groups.length ? groups : base;
  }
  if (base.length !== 1) return base;
  const single = base[0] || '';
  if (!single) return base;
  if (/--- Page \\d+ ---/.test(single)) {
    const parts = single
      .split(/--- Page \\d+ ---/)
      .map((part) => part.trim())
      .filter(Boolean);
    return parts.length ? parts : base;
  }
  if (single.includes('課程1') || single.includes('課程2')) return base;
  const pieces = single.split(/[、,，/／•・]/).map((part) => part.trim()).filter(Boolean);
  return pieces.length > 1 ? pieces : base;
}

function splitCourseValues(value, courseCount) {
  const lines = splitLines(value);
  if (!courseCount || courseCount <= 1) return lines.length ? [lines.join('\n')] : [''];
  const indexed = Array(courseCount).fill('');
  let matched = false;
  lines.forEach((line) => {
    const match = line.match(/^\u8ab2\u7a0b\s*(\d+)\s*[:\uff1a]\s*(.+)$/);
    if (!match) return;
    const idx = Number.parseInt(match[1], 10) - 1;
    if (Number.isNaN(idx) || idx < 0 || idx >= courseCount) return;
    indexed[idx] = match[2].trim();
    matched = true;
  });
  if (matched) return indexed;
  if (lines.length >= courseCount) return lines.slice(0, courseCount);
  return Array(courseCount).fill(lines.join('\n'));
}

function buildRowsFromBucket(bucket, options = {}) {
  const output = [];
  const courseIndex = Number.isInteger(options.courseIndex) ? options.courseIndex : null;
  const courseList = getCourseListFromBucket(bucket);
  const courseCount = courseList.length;

  FIELD_ORDER.forEach((fieldKey) => {
    const entry = bucket[fieldKey];
    const label = FIELD_META[fieldKey].label;

    if (!entry) {
      output.push({
        [COL_ITEM]: `${label}\uff1a${DISPLAY_MISSING_TEXT}`,
        [COL_PASS]: '-',
        [COL_FAIL]: DISPLAY_MISSING_TEXT,
        [COL_OTHER]: '-',
      });
      return;
    }

    if (fieldKey === 'course') {
      if (courseIndex !== null) {
        const course?? = courseList[courseIndex] || '';
        output.push({
          [COL_ITEM]: `\u8ab2\u7a0b${courseIndex + 1}\uff1a${course?? || DISPLAY_MISSING_TEXT}`,
          [COL_PASS]: entry.status === 'pass' ? '\u25cb' : '-',
          [COL_FAIL]: entry.status === 'fail' ? (entry.note || DISPLAY_MISSING_TEXT) : '-',
          [COL_OTHER]: '-',
        });
        return;
      }

      if (courseList.length) {
        courseList.forEach((course, index) => {
          output.push({
            [COL_ITEM]: `\u8ab2\u7a0b${index + 1}\uff1a${course}`,
            [COL_PASS]: entry.status === 'pass' ? '\u25cb' : '-',
            [COL_FAIL]: entry.status === 'fail' ? (entry.note || DISPLAY_MISSING_TEXT) : '-',
            [COL_OTHER]: '-',
          });
        });
      } else {
        output.push({
          [COL_ITEM]: `\u8ab2\u7a0b1\uff1a${DISPLAY_MISSING_TEXT}`,
          [COL_PASS]: '-',
          [COL_FAIL]: entry.status === 'fail' ? (entry.note || DISPLAY_MISSING_TEXT) : DISPLAY_MISSING_TEXT,
          [COL_OTHER]: '-',
        });
      }
      return;
    }

    let value = entry.value || '';
    if (courseIndex !== null && courseCount > 1 && value) {
      const perCourseValues = splitCourseValues(value, courseCount);
      value = perCourseValues[courseIndex] || '';
    }
    const itemText = value ? `${label}\uff1a${value}` : `${label}\uff1a${DISPLAY_MISSING_TEXT}`;

    output.push({
      [COL_ITEM]: itemText,
      [COL_PASS]: entry.status === 'pass' ? '\u25cb' : '-',
      [COL_FAIL]: entry.status === 'fail' ? (entry.note || DISPLAY_MISSING_TEXT) : '-',
      [COL_OTHER]: '-',
    });
  });

  return output;
}

function normalize??Rows(rawRows, feedbackText, context = {}, options = {}) {
  const bucket = build??Bucket(rawRows, feedbackText, context);
  return buildRowsFromBucket(bucket, options);
}

function resolveElements() {
  if (!form) form = document.getElementById('reviewForm');
  if (!resultEl) resultEl = document.getElementById('reviewResult');
}

function format??Status(status) {
  return STATUS_LABELS[status] || STATUS_LABELS.reviewing;
}

function build??TableElement(dataRows) {
  const headers = [COL_ITEM, COL_PASS, COL_FAIL, COL_OTHER];
  const table = document.createElement('table');
  table.class?? = 'ai-feedback-table';

  const thead = document.createElement('thead');
  const trh = document.createElement('tr');
  headers.forEach((header) => {
    const th = document.createElement('th');
    th.textContent = header;
    trh.appendChild(th);
  });
  thead.appendChild(trh);

  const tbody = document.createElement('tbody');
  dataRows.forEach((row) => {
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

function render??Table(rows, feedbackText, context = {}) {
  const bucket = build??Bucket(rows, feedbackText, context);
  const courseList = getCourseListFromBucket(bucket);
  const courseCount = courseList.length;
  if (courseCount > 1) {
    const wrap = document.createElement('div');
    wrap.class?? = 'table-wrap';
    courseList.forEach((course??, index) => {
      const label = document.createElement('div');
      label.class?? = 'review-label';
      label.textContent = `\u8ab2\u7a0b${index + 1}\uff1a${course?? || DISPLAY_MISSING_TEXT}`;
      wrap.appendChild(label);
      wrap.appendChild(build??TableElement(buildRowsFromBucket(bucket, { courseIndex: index })));
    });
    return wrap;
  }

  return build??TableElement(buildRowsFromBucket(bucket));
}



  function getFilterValues() {
    const time = document.getElementById('recordName')?.value || '';
    const studentId = document.getElementById('recordStudentId')?.value || '';
    const name = document.getElementById('recordName')?.value || '';

    const filters = {};
    if (time) filters.time = time.trim();
    if (studentId) filters.student_id = studentId.trim();
    if (name) filters.name = name.trim();
    return filters;
  }

window.get???????? = getFilterValues;

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
    td.class?? = 'empty';
    td.textContent = message;
    tr.appendChild(td);
    listEl.appendChild(tr);
  }

  async function fetch??(filters) {
    const params = new URL??Params();
    Object.entries(filters).forEach(([key, value]) => params.set(key, value));
    const url = `${API_BASE}/api/history/search?${params.toString()}`;
    const response = await fetch(url, { method: 'GET', credentials: 'include' });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    return data;
  }

  async function check??Access() {
    if (!is??Role()) return false;
    try {
      const res = await fetch(`${API_BASE}/api/labeling/unlabeled?limit=1&offset=0`, { credentials: 'include' });
      if (!res.ok) return false;
      return true;
    } catch (e) {
      return false;
    }
  }

  async function confirmRecord(record) {
    if (!window.confirm('是否確認送出，送出後不可更改')) return null;
    const res = await fetch(`${API_BASE}/api/history/confirm`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        applicantStdn: record.applicantStdn,
        applicantNo: record.applicantNo,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    return data.record || null;
  }

  function renderRows(records) {
    listEl.innerHTML = '';
    const currentUser = getStoredUser();
    const current??Id = (currentUser.studentId || '').trim();
    const confirmedRecord = records.find((item) => item?.isConfirmed);
    records.forEach((record) => {
      const tr = document.createElement('tr');
      tr.class?? = 'row-main';

      const td?? = document.createElement('td');
      td??.textContent = `${record.applyDate || ''} ${record.apply?? || ''}`.trim() || '-';

      const tdSid = document.createElement('td');
      tdSid.textContent = record.applicantStdn || '-';

      const td?? = document.createElement('td');
      td??.textContent = record.applicant?? || '-';

      const td???? = document.createElement('td');
      const finalPassed = record.finalIsPassed;
      const aiPassed = record.isPassed;
      let resultText = '-';
      if (finalPassed === true) resultText = '通過';
      else if (finalPassed === false) resultText = '不通過';
      else if (aiPassed === true) resultText = '通過';
      else if (aiPassed === false) resultText = '不通過';
      td????.textContent = resultText;

      const td?? = document.createElement('td');
      if (!teacherAccess) {
        const isOwner = current??Id
          && String(record.applicantStdn || '').trim().toLowerCase() === String(current??Id).trim().toLowerCase();
        const isConfirmed = !!record.isConfirmed;
        const blockedByOther = confirmedRecord && !isConfirmed;
        if (isOwner) {
          const confirmBtn = document.createElement('button');
          confirmBtn.type = 'button';
          confirmBtn.class?? = 'btn ghost sm';
          confirmBtn.textContent = isConfirmed ? '已提交' : '提交';
          confirmBtn.disabled = isConfirmed || blockedByOther;
          confirmBtn.addEventListener('click', async (e) => {
            e.stopPropagation();
            try {
              await confirmRecord(record);
              const data = await fetch??(getFilterValues());
              renderRows(data.records || []);
            } catch (error) {
      renderEmpty(error.message || '讀取失敗。', 6);
            }
          });
          td??.appendChild(confirmBtn);
        } else {
          td??.textContent = '-';
        }
      } else {
        td??.textContent = '-';
      }

      const tdAction = document.createElement('td');
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.class?? = 'btn ghost sm';
    btn.textContent = '檢視';
      tdAction.appendChild(btn);

      tr.appendChild(td??);
      tr.appendChild(tdSid);
      tr.appendChild(td??);
      tr.appendChild(td????);
      tr.appendChild(tdAction);
      tr.appendChild(td??);

      const details = document.createElement('tr');
      details.class?? = 'row-details is-hidden';
      const detailCell = document.createElement('td');
      detailCell.colSpan = 6;
      detailCell.class?? = 'detail-cell';

      const feedbackText = record.final?? || record.ai?? || '尚未產生結果';
      const tableRows = Array.isArray(record.final??Table) && record.final??Table.length ? record.final??Table : record.ai??Table;

      const summary = document.createElement('div');
      summary.class?? = 'fbx-summary';
      summary.textContent = feedbackText;
      detailCell.appendChild(summary);

      if (teacherAccess && record.applicantStdn && record.applicantNo !== undefined && record.applicantNo !== null) {
        const actions = document.createElement('div');
        actions.class?? = 'detail-actions';
        const editBtn = document.createElement('button');
        editBtn.type = 'button';
        editBtn.class?? = 'btn ghost sm';
    editBtn.textContent = '編輯';
        editBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          const qs = new URL??Params({
            applicantStdn: String(record.applicantStdn),
            applicantNo: String(record.applicantNo),
            source: 'history',
          });
          location.href = `label_detail.html?${qs.toString()}`;
        });
        actions.appendChild(editBtn);
        detailCell.appendChild(actions);
      }

      if (!teacherAccess) {
        // submit button is shown in main row
      }

      const divider = document.createElement('div');
      divider.class?? = 'divider';
      detailCell.appendChild(divider);
      detailCell.appendChild(render??Table(tableRows, feedbackText, { applicant??: record.applicant?? || '' }));

      details.appendChild(detailCell);

      btn.addEventListener('click', (event) => {
        event.stopPropagation();
        details.classList.toggle('is-hidden');
    btn.textContent = details.classList.contains('is-hidden') ? '檢視' : '收合';
      });

      listEl.appendChild(tr);
      listEl.appendChild(details);
    });
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    renderEmpty('載入中...', 6);
    try {
      teacherAccess = await check??Access();
      const data = await fetch??(getFilterValues());
      if (!data.records?.length) {
    renderEmpty('找不到資料。', 6);
        return;
      }
      renderRows(data.records);
    } catch (error) {
      renderEmpty(error.message || '讀取失敗。', 6);
    }
  });

  async function initialLoad() {
    renderEmpty('載入中...', 6);
    try {
      teacherAccess = await check??Access();
      const initial???? = {};
      if (!teacherAccess) {
        const currentUser = getStoredUser();
        const current??Id = (currentUser.studentId || '').trim();
        if (current??Id) {
          initial????.student_id = current??Id;
        }
        const studentInput = document.getElementById('recordStudentId');
        if (studentInput && current??Id) {
          studentInput.value = current??Id;
          studentInput.disabled = true;
        }
      }
      const data = await fetch??(initial????);
      if (!data.records?.length) {
    renderEmpty('找不到資料。', 6);
        return;
      }
      renderRows(data.records);
    } catch (error) {
      renderEmpty(error.message || '讀取失敗。', 6);
    }
  }

  initialLoad();
})();
