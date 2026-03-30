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

const MISSING_ITEM_TEXT = '未抓取到這個項目';
const DISPLAY_MISSING_TEXT = '未找到';

const STATUS_LABELS = {
  submitted: '\u5df2\u9001\u51fa',
  reviewing: '\u5be9\u6838\u4e2d',
  approved: '\u5be9\u6838\u901a\u904e',
  rejected: '\u5be9\u6838\u4e0d\u901a\u904e',
  returned: '\u5df2\u9000\u56de',
};

let form = null;
let resultEl = null;

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
    const resultText = pickFirst(row, ['result', '辨識結果', 'LLM 辨識結果', 'LLM辨識結果', '']);
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
    const resultText = pickFirst(row, ['result', '辨識結果', 'LLM 辨識結果', 'LLM辨識結果', '']);
      pickFirst(row, ['pass', 'Pass', '\u7b26\u5408', 'isPass', 'isPassed']),
    const failText = pickFirst(row, ['fail', 'Fail', '不符合']) || '-';
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
        [COL_ITEM]: `${label}：${DISPLAY_MISSING_TEXT}`,
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
          [COL_ITEM]: `課程${courseIndex + 1}：${course?? || DISPLAY_MISSING_TEXT}`,
          [COL_PASS]: course?? ? '○' : '-',
          [COL_FAIL]: course?? ? '-' : (entry.note || DISPLAY_MISSING_TEXT),
          [COL_OTHER]: '-',
        });
        return;
      }

      if (courseList.length) {
        courseList.forEach((course, index) => {
          output.push({
            [COL_ITEM]: `課程${index + 1}：${course}`,
            [COL_PASS]: entry.status === 'pass' ? '○' : '-',
            [COL_FAIL]: entry.status === 'fail' ? (entry.note || DISPLAY_MISSING_TEXT) : '-',
            [COL_OTHER]: '-',
          });
        });
      } else {
        output.push({
          [COL_ITEM]: `課程1：${DISPLAY_MISSING_TEXT}`,
          [COL_PASS]: '-',
          [COL_FAIL]: entry.status === 'fail' ? (entry.note || DISPLAY_MISSING_TEXT) : DISPLAY_MISSING_TEXT,
          [COL_OTHER]: '-',
        });
      }
      return;
    }

    let value = entry.value || '';
    if (courseIndex !== null && courseCount > 1) {
      const perCourseValues = splitCourseValues(value, courseCount);
      value = perCourseValues[courseIndex] || '';
    }
    const itemText = value ? `${label}：${value}` : `${label}：${DISPLAY_MISSING_TEXT}`;
    const rowPass = value ? '○' : '-';
    const rowFail = value ? '-' : (entry.note || DISPLAY_MISSING_TEXT);

    output.push({
      [COL_ITEM]: itemText,
      [COL_PASS]: courseIndex !== null && courseCount > 1 ? rowPass : (entry.status === 'pass' ? '○' : '-'),
      [COL_FAIL]: courseIndex !== null && courseCount > 1 ? rowFail : (entry.status === 'fail' ? (entry.note || DISPLAY_MISSING_TEXT) : '-'),
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

function render????(data) {
  resolveElements();
  if (!resultEl) return;
  resultEl.innerHTML = '';
  if (form && data?.applicantNo) {
    const caseInput = form.querySelector('input[name="caseNo"]');
    if (caseInput && !caseInput.value) {
      caseInput.value = String(data.applicantNo);
    }
  }

  const aiPassed = Boolean(data?.isPassed);
  const reviewStatus = data?.reviewStatus || 'submitted';
  const finalPassed = data?.finalIsPassed;
    const feedbackText = data?.final?? || data?.ai?? || '尚未產生結果';
  const tableRows = Array.isArray(data?.final??Table) && data.final??Table.length ? data.final??Table : data?.ai??Table;

  const wrap = document.createElement('div');
  wrap.class?? = 'review-result fbx';

  const header = document.createElement('div');
  header.class?? = 'fbx-hd';

  const statusPill = document.createElement('span');
  statusPill.class?? = 'pill neutral';
  statusPill.textContent = format??Status(reviewStatus);

  const aiPill = document.createElement('span');
  aiPill.class?? = `pill ${aiPassed ? 'ok' : 'ng'}`;
  aiPill.textContent = aiPassed ? 'AI \u5224\u5b9a\uff1a\u901a\u904e' : 'AI \u5224\u5b9a\uff1a\u672a\u901a\u904e';

  const title = document.createElement('div');
  title.class?? = 'review-label';
  title.textContent = '\u5be9\u6838\u7d50\u679c';

  header.appendChild(statusPill);
  header.appendChild(aiPill);
  header.appendChild(title);

  const summary = document.createElement('div');
  summary.class?? = 'fbx-summary';
  summary.textContent = feedbackText;

  const kv = document.createElement('div');
  kv.class?? = 'kv';
  const addKV = (key, value) => {
    const keyEl = document.createElement('div');
    keyEl.class?? = 'k';
    keyEl.textContent = key;
    const valueEl = document.createElement('div');
    valueEl.class?? = 'v';
    valueEl.textContent = value || '-';
    kv.appendChild(keyEl);
    kv.appendChild(valueEl);
  };

  addKV('\u7533\u8acb\u4eba', data?.applicant?? || '-');
  addKV('\u5b78\u865f', data?.applicantStdn || data?.studentId || '-');
  addKV('\u7533\u8acb\u65e5\u671f', data?.applyDate || '-');
  addKV('\u7533\u8acb\u6642\u9593', data?.apply?? || '-');
  addKV(
    '\u6559\u5e2b\u5224\u5b9a',
    reviewStatus === 'returned'
      ? '\u9000\u56de'
      : finalPassed === true
        ? '\u901a\u904e'
        : finalPassed === false
          ? '\u4e0d\u901a\u904e'
          : '\u5c1a\u672a\u5be9\u6838'
  );

  wrap.appendChild(header);
  wrap.appendChild(summary);
  wrap.appendChild(render??Table(tableRows, feedbackText, { applicant??: data?.applicant?? || '' }));
  wrap.appendChild(kv);
  resultEl.appendChild(wrap);
}

function renderError(message) {
  resolveElements();
  if (!resultEl) return;
  resultEl.textContent = message || '\u9001\u51fa\u5931\u6557\u3002';
}

function buildFormData(allowEmpty?? = false) {
  const fd = new FormData(form);
  const rawCaseNo = textOf(fd.get('caseNo'));
  if (!rawCaseNo || rawCaseNo === '系統自動產生' || !/^\d+$/.test(rawCaseNo)) {
    fd.delete('caseNo');
  }
  if (allowEmpty??) {
    const fileInput = form?.querySelector('input[name="file"]');
    if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
      fd.delete('file');
    }
  }
  return fd;
}

function validateBasic(fd) {
  const name = textOf(fd.get('name'));
  const studentId = textOf(fd.get('studentId'));
  if (!name || !studentId) {
      throw new Error('姓名與學號為必填。');
  }
}

function bind??() {
  resolveElements();
  if (!form) return;

  form.addEventListener('submit', async (event) => {
    event.preventDefault();

    const fd = buildFormData(true);
    try {
      validateBasic(fd);
    } catch (error) {
      renderError(error.message || '\u9001\u51fa\u5931\u6557\u3002');
      return;
    }
    const studentId = textOf(fd.get('studentId'));
    if (studentId) localStorage.setItem('studentId', studentId);

    resultEl.textContent = '\u9001\u51fa\u4e2d...';
    try {
      const caseNo = textOf(fd.get('caseNo'));
      let response;
      let data;
      const controller = new AbortController();
      const timeoutId = set??out(() => controller.abort(), 180000);
      const doFetch = async (url) => fetch(url, {
        method: 'POST',
        body: fd,
        credentials: 'include',
        signal: controller.signal,
      });

      if (caseNo) {
        response = await doFetch(`${API_BASE}/api/analyzeApplication/review`);
        data = await response.json();
        if (!response.ok && response.status === 404) {
          response = await doFetch(`${API_BASE}/api/analyzeApplication`);
          data = await response.json();
        }
      } else {
        response = await doFetch(`${API_BASE}/api/analyzeApplication`);
        data = await response.json();
      }
      clear??out(timeoutId);
      if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
      render????(data);
    } catch (error) {
      if (error && error.name === 'AbortError') {
        renderError('\u8655\u7406\u6642\u9593\u904e\u9577\uff0c\u8acb\u7a0d\u5f8c\u518d\u8a66\u3002');
        return;
      }
      renderError(error.message || '\u9001\u51fa\u5931\u6557\u3002');
    }
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', bind??);
} else {
  bind??();
}
