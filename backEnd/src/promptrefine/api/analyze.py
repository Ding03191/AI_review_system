import json
import os
from zoneinfo import ZoneInfo
import re
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request
from openai import OpenAI
from pdf2image import convert_from_path
from PIL import ImageEnhance, ImageFilter, ImageOps, ImageStat
from PyPDF2 import PdfReader
import pdfplumber
import pytesseract

from ..db import dbStoring as db

analyze_bp = Blueprint("analyze", __name__)

_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_ATTACHMENTS_DIR = os.path.join(_BACKEND_DIR, "attachments")
_MAX_TEXT_CHARS = 20000
_OCR_MAX_PAGES = int(os.environ.get("OCR_MAX_PAGES", "6"))
_ENHANCE_DPI = int(os.environ.get("PDF_ENHANCE_DPI", "350"))

_COURSE_TITLE_LINE_RE = re.compile(r"((?:\u8ab2\u7a0b\u540d\u7a31|\u8ab2\u7a0b\u6a19\u984c)\s*[:\uff1a]\s*)([^\n]+)")
_SUSPECT_TITLE_RE = re.compile(r"([\u4e00-\u9fffA-Za-z0-9]+)\s*[|\uff5c]\s*([\u4e00-\u9fffA-Za-z0-9][^\n]*)")
_FULL_WIDTH_PAREN_RE = re.compile(r"\uff08\s*([\u4e00-\u9fffA-Za-z0-9]{1,12})\s*\uff09(?=[\u4e00-\u9fffA-Za-z0-9])")
_HALF_WIDTH_PAREN_RE = re.compile(r"\(\s*([\u4e00-\u9fffA-Za-z0-9]{1,12})\s*\)(?=[\u4e00-\u9fffA-Za-z0-9])")
_MISSING_LEFT_BRACKET_RE = re.compile(r"(?<![\[\uff3b\u3010\(\uff08])([\u4e00-\u9fffA-Za-z0-9]{1,12})\s*[\]\uff3d\u3011](?=[\u4e00-\u9fffA-Za-z0-9])")
_MISSING_RIGHT_BRACKET_RE = re.compile(r"(?<![\[\uff3b\u3010\(\uff08])([\u4e00-\u9fffA-Za-z0-9]{1,12})\s*[|\uff5c](?=[\u4e00-\u9fffA-Za-z0-9])")


def _fix_course_title_text(title_text):
    title = (title_text or "").strip()
    if not title:
        return title

    title = _FULL_WIDTH_PAREN_RE.sub(r"[\1]", title)
    title = _HALF_WIDTH_PAREN_RE.sub(r"[\1]", title)
    title = _MISSING_LEFT_BRACKET_RE.sub(r"[\1]", title)
    title = _MISSING_RIGHT_BRACKET_RE.sub(r"[\1]", title)

    def replace_bar(match):
        left = match.group(1).strip()
        right = match.group(2).strip()
        return f"[{left}]{right}" if len(left) <= 12 else match.group(0)

    title = _SUSPECT_TITLE_RE.sub(replace_bar, title)
    title = re.sub(r"\[\s+", "[", title)
    title = re.sub(r"\s+\]", "]", title)
    return title


def _normalize_course_title_symbols(text):
    source = text or ""
    if not source:
        return source

    def replace_line(match):
        return f"{match.group(1)}{_fix_course_title_text(match.group(2))}"

    return _COURSE_TITLE_LINE_RE.sub(replace_line, source)


def _extract_text_pages(pdf_path):
    pages = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                pages.append((page.extract_text() or "").strip())
    except Exception:
        pages = []

    if any(pages):
        return pages

    try:
        reader = PdfReader(pdf_path)
        return [(page.extract_text() or "").strip() for page in reader.pages]
    except Exception:
        return []


def _enhance_pdf_for_ai(pdf_path):
    if not pdf_path.lower().endswith(".pdf"):
        return pdf_path

    enhanced_path = f"{os.path.splitext(pdf_path)[0]}_enhanced.pdf"
    try:
        images = convert_from_path(pdf_path, dpi=_ENHANCE_DPI)
    except Exception:
        return pdf_path

    if not images:
        return pdf_path

    enhanced_images = []
    for image in images:
        try:
            if image.mode != "RGB":
                image = image.convert("RGB")
            image = image.filter(ImageFilter.UnsharpMask(radius=1.5, percent=150, threshold=3))
        except Exception:
            pass
        enhanced_images.append(image)

    try:
        enhanced_images[0].save(
            enhanced_path,
            save_all=True,
            append_images=enhanced_images[1:],
            resolution=_ENHANCE_DPI,
        )
    except Exception:
        return pdf_path

    return enhanced_path


def _prepare_ocr_variants(image):
    variants = []

    try:
        base = image.convert("RGB") if image.mode != "RGB" else image.copy()
    except Exception:
        base = image

    variants.append(base)

    try:
        gray = ImageOps.grayscale(base)
        contrast = ImageEnhance.Contrast(gray).enhance(2.2)
        sharp = contrast.filter(ImageFilter.UnsharpMask(radius=1.5, percent=180, threshold=2))
        variants.append(sharp)
    except Exception:
        pass

    try:
        gray = ImageOps.grayscale(base)
        stat = ImageStat.Stat(gray)
        mean_brightness = stat.mean[0] if stat.mean else 255
        hist = gray.histogram()
        dark_ratio = (sum(hist[:70]) / (sum(hist) or 1)) if hist else 0.0

        if mean_brightness < 110 or dark_ratio > 0.45:
            inverted = ImageOps.invert(gray)
            inverted = ImageEnhance.Contrast(inverted).enhance(2.6)
            inverted = inverted.filter(ImageFilter.UnsharpMask(radius=1.2, percent=200, threshold=2))
            variants.append(inverted)

            width, height = gray.size
            top_band = gray.crop((0, 0, width, max(1, int(height * 0.12))))
            top_mean = (ImageStat.Stat(top_band).mean or [mean_brightness])[0]
            if height > 400 and top_mean < 90:
                cropped = gray.crop((0, int(height * 0.1), width, height))
                cropped = ImageOps.invert(cropped)
                cropped = ImageEnhance.Contrast(cropped).enhance(2.8)
                cropped = cropped.filter(ImageFilter.UnsharpMask(radius=1.2, percent=200, threshold=2))
                variants.append(cropped)
    except Exception:
        pass

    deduped = []
    seen = set()
    for variant in variants:
        try:
            signature = (variant.mode, variant.size, variant.tobytes()[:128])
        except Exception:
            signature = id(variant)
        if signature in seen:
            continue
        seen.add(signature)
        deduped.append(variant)
    return deduped


def _ocr_image_best_effort(image):
    best_text = ""
    best_score = -1

    for variant in _prepare_ocr_variants(image):
        try:
            text = pytesseract.image_to_string(variant, lang="chi_tra+eng")
        except Exception:
            text = ""
        text = (text or "").strip()
        if not text:
            continue

        score = len(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]", text))
        if score > best_score:
            best_score = score
            best_text = text

    return best_text


def _ocr_pdf_pages(pdf_path):
    tesseract_cmd = os.environ.get("TESSERACT_CMD")
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    try:
        images = convert_from_path(pdf_path, dpi=300, first_page=1, last_page=_OCR_MAX_PAGES)
    except Exception:
        return []

    return [_ocr_image_best_effort(image) for image in images]


def _extract_pdf_text(pdf_path):
    extracted_pages = _extract_text_pages(pdf_path)
    enhanced_path = _enhance_pdf_for_ai(pdf_path)
    extracted_text = "\n".join((page or "") for page in extracted_pages)
    extracted_score = len(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]", extracted_text))

    ocr_pages = []
    if extracted_score < 200:
        ocr_pages = _ocr_pdf_pages(enhanced_path)

    page_count = max(len(extracted_pages), len(ocr_pages))
    merged_pages = []

    for idx in range(page_count):
        blocks = []
        text_page = extracted_pages[idx].strip() if idx < len(extracted_pages) else ""
        ocr_page = ocr_pages[idx].strip() if idx < len(ocr_pages) else ""

        if text_page:
            blocks.append("[TEXT]\n" + text_page)
        if ocr_page:
            blocks.append("[OCR]\n" + ocr_page)
        if blocks:
            merged_pages.append(f"--- Page {idx + 1} ---\n" + "\n\n".join(blocks))

    text = "\n\n".join(merged_pages).strip()
    if len(text) > _MAX_TEXT_CHARS:
        text = text[:_MAX_TEXT_CHARS]
    return _normalize_course_title_symbols(text)


def _parse_ai_json(raw_text):
    if not raw_text:
        return None
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            return json.loads(raw_text[start:end + 1])
        except json.JSONDecodeError:
            return None


def _load_system_prompt():
    return (
        "You are a strict academic certificate reviewer. "
        "Read every PDF page carefully. The PDF text contains explicit page markers like '--- Page 1 ---'. "
        "Use both [TEXT] and [OCR] content together. "
        "Reply in Traditional Chinese and return JSON only, no markdown. "
        "The JSON schema is: "
        "{"
        "\"isPassed\": true or false, "
        "\"aiFeedback\": \"Traditional Chinese summary\", "
        "\"aiFeedbackTable\": ["
        "{"
        "\"item\": \"中文姓名|課程名稱|課程期間|有無測驗|適用對象\", "
        "\"result\": \"exact extracted value\", "
        "\"pass\": \"○ or -\", "
        "\"fail\": \"brief failure reason or -\", "
        "\"other\": \"未抓取到這個項目 or -\""
        "}"
        "]"
        "}. "
        "Important rules: "
        "1. You must explicitly extract and show the exact Chinese name if found on the certificate. "
        "2. You must list every course name found across all PDF pages. "
        "3. Do not merge different fields into one row. "
        "4. If a field has an extracted value and there is no clear violation, mark pass as ○. "
        "5. If a field is missing, result should be empty and other should be '未抓取到這個項目'. "
        "6. For course names, result should only contain the course titles, not hours, scores, or extra commentary."
    )


def _normalize_courses(raw_list):
    courses = []
    seen = set()
    duplicates = []
    for item in raw_list:
        name = (item or "").strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            duplicates.append(name)
            continue
        seen.add(key)
        courses.append(name)
    return courses, duplicates


def _load_system_prompt():
    return (
        "You are a strict academic certificate reviewer. "
        "Read every PDF page carefully. The PDF text contains explicit page markers like '--- Page 1 ---'. "
        "Use both [TEXT] and [OCR] content together. "
        "Reply in Traditional Chinese and return JSON only, no markdown. "
        "The JSON schema is: "
        "{"
        "\"isPassed\": true or false, "
        "\"aiFeedback\": \"Traditional Chinese summary\", "
        "\"aiFeedbackTable\": ["
        "{"
        "\"item\": \"中文姓名|課程名稱|課程期間|有無測驗|適用對象\", "
        "\"result\": \"exact extracted value\", "
        "\"pass\": \"○ or -\", "
        "\"fail\": \"brief failure reason or -\", "
        "\"other\": \"未抓取到這個項目 or -\""
        "}"
        "]"
        "}. "
        "Important rules: "
        "1. You must explicitly extract and show the exact Chinese name if found on the certificate. "
        "2. You must list every course name found across all PDF pages. "
        "3. Do not merge different fields into one row. "
        "4. If a field has an extracted value and there is no clear violation, mark pass as ○. "
        "5. If a field is missing, result should be empty and other should be '未抓取到這個項目'. "
        "6. For course names, result should only contain the course titles, not hours, scores, or extra commentary."
    )


def _expand_compound_feedback_rows(rows):
    if not isinstance(rows, list):
        return []

    expanded = []
    expected_items = ["中文姓名", "課程名稱", "課程期間", "有無測驗", "適用對象"]

    for row in rows:
        if not isinstance(row, dict):
            continue

        item_text = str(row.get("item") or "").strip()
        result_text = str(row.get("result") or "").strip()
        pass_text = str(row.get("pass") or "").strip() or "-"
        fail_text = str(row.get("fail") or "").strip() or "-"
        other_text = str(row.get("other") or "").strip() or "-"

        item_parts = [part.strip() for part in re.split(r"[|｜]", item_text) if part.strip()]
        result_parts = [part.strip() for part in re.split(r"[|｜]", result_text)]

        if item_parts == expected_items and len(result_parts) >= len(expected_items):
            for index, item_name in enumerate(expected_items):
                value = result_parts[index].strip() if index < len(result_parts) else ""
                expanded.append(
                    {
                        "item": item_name,
                        "result": "" if value == "未抓取到這個項目" else value,
                        "pass": pass_text if value and value != "未抓取到這個項目" else "-",
                        "fail": fail_text if fail_text != "-" and item_name != "中文姓名" else "-",
                        "other": other_text if not value or value == "未抓取到這個項目" else "-",
                    }
                )
            continue

        expanded.append(row)

    return expanded


def _load_system_prompt():
    return (
        "You are a strict academic certificate reviewer. "
        "Read every PDF page carefully. The PDF text contains explicit page markers like '--- Page 1 ---'. "
        "Use both [TEXT] and [OCR] content together. "
        "Reply in Traditional Chinese and return JSON only, no markdown. "
        "The JSON schema is: "
        "{"
        "\"isPassed\": true or false, "
        "\"aiFeedback\": \"Traditional Chinese summary\", "
        "\"aiFeedbackTable\": ["
        "{"
        "\"item\": \"\\u4e2d\\u6587\\u59d3\\u540d|\\u8ab2\\u7a0b\\u540d\\u7a31|\\u8ab2\\u7a0b\\u671f\\u9593|\\u6709\\u7121\\u6e2c\\u9a57|\\u9069\\u7528\\u5c0d\\u8c61\", "
        "\"result\": \"exact extracted value\", "
        "\"pass\": \"\\u25cb or -\", "
        "\"fail\": \"brief failure reason or -\", "
        "\"other\": \"\\u672a\\u6293\\u53d6\\u5230\\u9019\\u500b\\u9805\\u76ee or -\""
        "}"
        "]"
        "}. "
        "Important rules: "
        "1. You must explicitly extract and show the exact Chinese name if found on the certificate. "
        "2. You must list every course name found across all PDF pages. "
        "3. Do not merge different fields into one row. "
        "4. If a field has an extracted value and there is no clear violation, mark pass as \\u25cb. "
        "5. If a field is missing, result should be empty and other should be '\\u672a\\u6293\\u53d6\\u5230\\u9019\\u500b\\u9805\\u76ee'. "
        "6. For course names, result should only contain the course titles, not hours, scores, or extra commentary."
    )


def _expand_compound_feedback_rows(rows):
    if not isinstance(rows, list):
        return []

    expected_items = [
        "\u4e2d\u6587\u59d3\u540d",
        "\u8ab2\u7a0b\u540d\u7a31",
        "\u8ab2\u7a0b\u671f\u9593",
        "\u6709\u7121\u6e2c\u9a57",
        "\u9069\u7528\u5c0d\u8c61",
    ]
    missing_text = "\u672a\u6293\u53d6\u5230\u9019\u500b\u9805\u76ee"
    name_item = "\u4e2d\u6587\u59d3\u540d"
    expanded = []

    for row in rows:
        if not isinstance(row, dict):
            continue

        item_text = str(row.get("item") or "").strip()
        result_text = str(row.get("result") or "").strip()
        pass_text = str(row.get("pass") or "").strip() or "-"
        fail_text = str(row.get("fail") or "").strip() or "-"
        other_text = str(row.get("other") or "").strip() or "-"

        item_parts = [part.strip() for part in re.split(r"[|\uff5c]", item_text) if part.strip()]
        result_parts = [part.strip() for part in re.split(r"[|\uff5c]", result_text)]

        if item_parts == expected_items and len(result_parts) >= len(expected_items):
            for index, item_name in enumerate(expected_items):
                value = result_parts[index].strip() if index < len(result_parts) else ""
                expanded.append(
                    {
                        "item": item_name,
                        "result": "" if value == missing_text else value,
                        "pass": pass_text if value and value != missing_text else "-",
                        "fail": fail_text if fail_text != "-" and item_name != name_item else "-",
                        "other": other_text if not value or value == missing_text else "-",
                    }
                )
            continue

        expanded.append(row)

    return expanded


def _extract_target_from_text(pdf_text):
    if not pdf_text:
        return ""

    lines = [line.strip() for line in str(pdf_text).splitlines()]
    for idx, line in enumerate(lines):
        if "\u9069\u7528\u5c0d\u8c61" not in line:
            continue

        collected = []
        parts = re.split(r"[:\uff1a]", line, maxsplit=1)
        if len(parts) > 1 and parts[1].strip():
            collected.append(parts[1].strip())

        for j in range(idx + 1, min(idx + 4, len(lines))):
            nxt = lines[j].strip()
            if not nxt:
                break
            if re.search(r"(\u8ab2\u7a0b|\u4e0a\u8ab2|\u6e2c\u9a57|\u8a8d\u8b49|\u5b78\u54e1\u59d3\u540d|\u958b\u8ab2|\u901a\u904e|\u767c\u8b49)", nxt):
                break
            collected.append(nxt)

        value = "\u3001".join([c for c in collected if c])
        if value:
            return _ensure_higher_edu_target(value, pdf_text)

    return ""


def _ensure_higher_edu_target(target_text, pdf_text):
    if not target_text:
        return target_text

    higher_edu_keywords = [
        "\u5927\u5b78",
        "\u5927\u5c08",
        "\u5c08\u79d1",
        "\u5927\u5c08\u9662\u6821",
        "\u5927\u5b78\u90e8",
        "\u7814\u7a76\u6240",
        "\u535a\u58eb\u73ed",
        "\u78a9\u58eb\u73ed",
        "\u5b78\u9662",
    ]

    has_higher_edu = any(keyword in target_text for keyword in higher_edu_keywords)
    if has_higher_edu:
        return target_text

    if any(keyword in pdf_text for keyword in higher_edu_keywords):
        return f"{target_text}\u3001\u5927\u5c08\u9662\u6821"

    return target_text


def _has_target_value(rows):
    missing_text = "\u672a\u6293\u53d6\u5230\u9019\u500b\u9805\u76ee"
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        item = str(row.get("item") or "")
        result = str(row.get("result") or "").strip()
        if "\u9069\u7528\u5c0d\u8c61" in item and result and result != missing_text:
            return True
    return False


def _analyze_with_ai(pdf_text, form_data):
    api_key = current_app.config.get("OPENAI_API_KEY")
    if not api_key:
        return {"isPassed": False, "aiFeedback": "OPENAI_API_KEY not set.", "aiFeedbackTable": []}

    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    client = OpenAI(api_key=api_key)

    system_prompt = _load_system_prompt()
    user_prompt = (
        "Review the uploaded application PDF.\n\n"
        "Form data:\n"
        f"- Case No: {form_data.get('caseNo')}\n"
        f"- Name: {form_data.get('name')}\n"
        f"- Student ID: {form_data.get('studentId')}\n"
        f"- Courses from form: {', '.join(form_data.getlist('courses')) or '(none)'}\n\n"
        "Tasks:\n"
        "- Check every page.\n"
        "- Extract the exact certificate name if present.\n"
        "- Extract every course title from all pages.\n"
        "- Keep course titles separate from hours, scores, and target audience.\n"
        "- Return the table rows in the requested JSON schema.\n\n"
        f"PDF content:\n{pdf_text}\n"
    )

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
    )

    content = (resp.choices[0].message.content or "").strip()
    parsed = _parse_ai_json(content)
    if not parsed:
        return {"isPassed": False, "aiFeedback": "AI response is invalid.", "aiFeedbackTable": []}

    is_passed = parsed.get("isPassed", False)
    if isinstance(is_passed, str):
        is_passed = is_passed.strip().lower() == "true"

    feedback = parsed.get("aiFeedback", "AI feedback missing.")
    if isinstance(feedback, list):
        feedback = "\n".join(str(item) for item in feedback if item is not None).strip()
    elif not isinstance(feedback, str):
        feedback = json.dumps(feedback, ensure_ascii=False)
    if not feedback:
        feedback = "AI feedback missing."

    table_rows = parsed.get("aiFeedbackTable") or parsed.get("aiFeedbackTableRows") or []
    if not isinstance(table_rows, list):
        table_rows = []
    table_rows = _expand_compound_feedback_rows(table_rows)
    if not _has_target_value(table_rows):
        target_text = _extract_target_from_text(pdf_text)
        if target_text:
            table_rows.append(
                {
                    "item": "\u9069\u7528\u5c0d\u8c61",
                    "result": target_text,
                    "pass": "\u25cb",
                    "fail": "-",
                    "other": "-",
                }
            )
        else:
            table_rows.append(
                {
                    "item": "\u9069\u7528\u5c0d\u8c61",
                    "result": "",
                    "pass": "-",
                    "fail": "\u672a\u6293\u53d6\u5230\u9019\u500b\u9805\u76ee",
                    "other": "\u672a\u6293\u53d6\u5230\u9019\u500b\u9805\u76ee",
                }
            )

    def _t(value):
        if value is None:
            return ""
        return str(value).strip()

    def _is_blank(value):
        text = _t(value)
        return not text or text in {"-", "null", "undefined"}

    def _is_marked(value):
        text = _t(value).lower()
        return text in {"○", "◯", "o", "yes", "y", "true", "1", "pass", "passed", "符合", "是"}

    def _is_failure_cell(value):
        text = _t(value)
        if _is_blank(text):
            return False
        if text == "-":
            return False
        return True

    def _row_failed(row):
        pass_text = _t(row.get("pass"))
        fail_text = _t(row.get("fail"))
        other_text = _t(row.get("other"))

        if _is_marked(pass_text) and not _is_failure_cell(fail_text) and not _is_failure_cell(other_text):
            return False

        if _is_failure_cell(fail_text) or _is_failure_cell(other_text):
            return True

        return True

        return True

    if table_rows:
        is_passed = not any(_row_failed(row) for row in table_rows)

    return {
        "isPassed": bool(is_passed),
        "aiFeedback": feedback,
        "aiFeedbackTable": table_rows,
    }


@analyze_bp.route("/api/analyzeApplication", methods=["POST"])
def analyze_application():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded."}), 400

    uploaded_file = request.files["file"]
    filename = uploaded_file.filename or "uploaded"
    ext = os.path.splitext(filename)[1].lower().lstrip(".")
    if ext and ext not in current_app.config["ALLOWED_EXTENSIONS"]:
        return jsonify({"error": "Unsupported file type. Allowed: pdf, doc, docx"}), 400

    os.makedirs(_ATTACHMENTS_DIR, exist_ok=True)
    safe_name = filename.replace(" ", "_")
    saved_file_path = os.path.join(_ATTACHMENTS_DIR, safe_name)
    uploaded_file.save(saved_file_path)

    now = datetime.now(ZoneInfo("Asia/Taipei"))
    apply_date = now.strftime("%Y-%m-%d")
    apply_time = now.strftime("%H:%M")

    applicant_no = (request.form.get("caseNo") or "").strip()
    applicant_name = (request.form.get("name") or "").strip()
    applicant_stdn = (request.form.get("studentId") or "").strip()
    raw_courses = request.form.getlist("courses")
    course_list, duplicates = _normalize_courses(raw_courses)
    course_name = ", ".join(course_list)

    if not applicant_name or not applicant_stdn:
        return jsonify({"error": "name and studentId are required."}), 400
    if duplicates:
        return jsonify({"error": "Duplicate course names are not allowed."}), 400

    confirmed = db.get_confirmed_record(applicant_stdn)
    if confirmed:
        return jsonify({"error": "A record has already been submitted."}), 409

    if not applicant_no:
        applicant_no_value = db.get_next_case_no()
        applicant_no = str(applicant_no_value)
    else:
        applicant_no_value = int(applicant_no) if applicant_no.isdigit() else applicant_no
    if db.has_history_record(applicant_stdn, applicant_no_value):
        return jsonify({"error": "Case already exists. Please submit a new case number."}), 409

    result_json = {
        "applicantStdn": applicant_stdn,
        "applicantNo": applicant_no_value,
        "applicantName": applicant_name,
        "course_name": course_name,
        "file_name": safe_name,
        "pdf_path": f"attachments/{safe_name}",
        "isPassed": False,
        "aiFeedback": "AI review pending.",
        "aiFeedbackTable": [],
        "reviewStatus": "submitted",
        "finalIsPassed": None,
        "finalFeedback": None,
        "finalFeedbackTable": None,
        "reviewedAt": None,
        "applyDate": apply_date,
        "applyTime": apply_time,
    }

    pdf_text = _extract_pdf_text(saved_file_path)
    ai_result = _analyze_with_ai(pdf_text, request.form)
    result_json["isPassed"] = ai_result.get("isPassed", False)
    result_json["aiFeedback"] = ai_result.get("aiFeedback", result_json["aiFeedback"])
    result_json["aiFeedbackTable"] = ai_result.get("aiFeedbackTable", result_json["aiFeedbackTable"])

    db.insert_scoring_result(result_json)
    return jsonify(result_json), 200
