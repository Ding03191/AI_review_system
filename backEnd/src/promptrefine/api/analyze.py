import json
import os
from datetime import datetime
from flask import Blueprint, current_app, jsonify, request
import pdfplumber
from PyPDF2 import PdfReader
from openai import OpenAI
from pdf2image import convert_from_path
import pytesseract

from ..db import dbStoring as db

analyze_bp = Blueprint('analyze', __name__)

_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_ATTACHMENTS_DIR = os.path.join(_BACKEND_DIR, 'attachments')
_MAX_TEXT_CHARS = 20000
_OCR_MAX_PAGES = int(os.environ.get("OCR_MAX_PAGES", "6"))


def _extract_pdf_text(pdf_path):
    text_parts = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text_parts.append(page.extract_text() or '')
    except Exception:
        text_parts = []

    if not ''.join(text_parts).strip():
        try:
            reader = PdfReader(pdf_path)
            for page in reader.pages:
                text_parts.append(page.extract_text() or '')
        except Exception:
            text_parts = []

    text = '\n'.join(text_parts).strip()
    if not text:
        text = _ocr_pdf_text(pdf_path)
    if len(text) > _MAX_TEXT_CHARS:
        text = text[:_MAX_TEXT_CHARS]
    return text


def _ocr_pdf_text(pdf_path):
    tesseract_cmd = os.environ.get("TESSERACT_CMD")
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    text_parts = []
    try:
        images = convert_from_path(pdf_path, dpi=300, first_page=1, last_page=_OCR_MAX_PAGES)
    except Exception:
        return ""

    for image in images:
        try:
            page_text = pytesseract.image_to_string(image, lang="chi_tra+eng")
        except Exception:
            page_text = ""
        if page_text:
            text_parts.append(page_text)

    return '\n'.join(text_parts).strip()


def _parse_ai_json(raw_text):
    if not raw_text:
        return None
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        start = raw_text.find('{')
        end = raw_text.rfind('}')
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            return json.loads(raw_text[start:end + 1])
        except json.JSONDecodeError:
            return None


def _analyze_with_ai(pdf_text, form_data):
    api_key = current_app.config.get("OPENAI_API_KEY")
    if not api_key:
        return {"isPassed": False, "aiFeedback": "未設定 OPENAI_API_KEY，無法進行 AI 審核。"}

    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    client = OpenAI(api_key=api_key)

    system_prompt = (
        "你是審核員，必須以繁體中文輸出審核結果。"
        "只回傳 JSON（不要 markdown），欄位包含 isPassed（true/false）與 aiFeedback（條列式理由）。"
    )
    user_prompt = (
        "請根據以下 PDF 內容與表單資料進行審核，回傳 JSON。\n\n"
        f"表單資料：\n"
        f"- 案件編號: {form_data.get('caseNo')}\n"
        f"- 申請人姓名: {form_data.get('name')}\n"
        f"- 學號: {form_data.get('studentId')}\n"
        f"- 學習項目: {form_data.get('project')}\n"
        f"- 特色或產業需求: {form_data.get('feature')}\n"
        f"- 課程名稱: {', '.join(form_data.getlist('courses'))}\n"
        f"- 總時數: {form_data.get('totalHours')}\n"
        f"- 永續目標: {form_data.get('sdg_values')}\n"
        f"- 課程主題: {', '.join(form_data.getlist('topics'))}\n\n"
        f"PDF 內容（可能不完整）：\n{pdf_text}\n"
    )

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )
    content = (resp.choices[0].message.content or "").strip()
    parsed = _parse_ai_json(content)
    if not parsed:
        return {"isPassed": False, "aiFeedback": "AI 回傳格式錯誤，無法解析。"}

    is_passed = parsed.get("isPassed", False)
    if isinstance(is_passed, str):
        is_passed = is_passed.strip().lower() == "true"
    feedback = parsed.get("aiFeedback", "AI 未提供審核說明。")
    if isinstance(feedback, list):
        feedback = '\n'.join(str(item) for item in feedback if item is not None).strip()
    elif not isinstance(feedback, str):
        feedback = json.dumps(feedback, ensure_ascii=False)
    if not feedback:
        feedback = "AI 未提供審核說明。"
    return {
        "isPassed": bool(is_passed),
        "aiFeedback": feedback,
    }


@analyze_bp.route('/python-api/analyzeApplication', methods=['POST'])
def analyze_application():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded.'}), 400

    uploaded_file = request.files['file']
    filename = uploaded_file.filename or 'uploaded'
    ext = os.path.splitext(filename)[1].lower().lstrip('.')
    if ext and ext not in current_app.config['ALLOWED_EXTENSIONS']:
        return jsonify({'error': 'Unsupported file type. Allowed: pdf, doc, docx'}), 400

    os.makedirs(_ATTACHMENTS_DIR, exist_ok=True)
    safe_name = filename.replace(' ', '_')
    saved_file_path = os.path.join(_ATTACHMENTS_DIR, safe_name)
    uploaded_file.save(saved_file_path)

    now = datetime.now()
    apply_date = now.strftime('%Y-%m-%d')
    apply_time = now.strftime('%H:%M')

    applicant_no = (request.form.get('caseNo') or '').strip()
    applicant_name = (request.form.get('name') or '').strip()
    applicant_stdn = (request.form.get('studentId') or '').strip()
    course_list = [c for c in request.form.getlist('courses') if c.strip()]
    course_name = ', '.join(course_list)
    if not applicant_no or not applicant_name or not applicant_stdn:
        return jsonify({'error': 'Missing required applicant fields.'}), 400

    result_json = {
        'applicantStdn': applicant_stdn,
        'applicantNo': int(applicant_no) if applicant_no.isdigit() else applicant_no,
        'applicantName': applicant_name,
        'course_name': course_name,
        'file_name': safe_name,
        'pdf_path': f'attachments/{safe_name}',
        'isPassed': False,
        'aiFeedback': '尚未進行 AI 審核。',
        'applyDate': apply_date,
        'applyTime': apply_time,
    }

    pdf_text = _extract_pdf_text(saved_file_path)
    ai_result = _analyze_with_ai(pdf_text, request.form)
    result_json['isPassed'] = ai_result.get('isPassed', False)
    result_json['aiFeedback'] = ai_result.get('aiFeedback', result_json['aiFeedback'])

    db.insert_scoring_result(result_json)
    return jsonify(result_json), 200
