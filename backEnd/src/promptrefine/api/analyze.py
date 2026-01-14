import json
import os
import re
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request

from ..db import dbStoring as db
from ..services import ai_service as da
from ..utils.guardrails import (
    RETRIEVAL_SIM_THRESHOLD,
    overall_business_rules,
    post_validate,
    preflight_from_upload,
)
from ..utils.rag_utils import ask_rag


analyze_bp = Blueprint("analyze", __name__)

_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_ATTACHMENTS_DIR = os.path.join(_BACKEND_DIR, "attachments")


@analyze_bp.route("/python-api/analyzeApplication", methods=["POST"])
def generate_application_feedback():
    def sanitize_chinese_filename(filename):
        name, ext = os.path.splitext(filename)
        name = re.sub(r"[^\u4e00-\u9fff\w\-]+", "_", name)
        name = name.strip("_") or "uploaded"
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"{name}_{timestamp}{ext}"

    def _is_allowed(filename):
        ext = os.path.splitext(filename)[1].lower().lstrip(".")
        return ext in current_app.config["ALLOWED_EXTENSIONS"]

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded."}), 400

    max_upload_size = current_app.config["MAX_UPLOAD_SIZE"]
    if request.content_length and request.content_length > max_upload_size:
        return jsonify({"error": f"File too large. Max {max_upload_size // (1024 * 1024)} MB"}), 413

    instruction = request.form.get("instruction", "")
    courses = request.form.getlist("courses")
    current_app.logger.info("收到課程列表：%s", courses)

    uploaded_file = request.files["file"]
    original_filename = uploaded_file.filename
    if not _is_allowed(original_filename):
        return jsonify({"error": "Unsupported file type. Allowed: pdf, doc, docx"}), 400

    uploaded_file.stream.seek(0, os.SEEK_END)
    size_bytes = uploaded_file.stream.tell()
    uploaded_file.stream.seek(0)
    if size_bytes and size_bytes > max_upload_size:
        return jsonify({"error": f"File too large. Max {max_upload_size // (1024 * 1024)} MB"}), 413

    filename = sanitize_chinese_filename(original_filename)

    os.makedirs(_ATTACHMENTS_DIR, exist_ok=True)
    saved_file_path = os.path.join(_ATTACHMENTS_DIR, filename)
    uploaded_file.save(saved_file_path)

    try:
        file_content = da.extract_file_content(saved_file_path)
        if file_content.startswith("Error") or file_content.startswith("Unsupported"):
            return jsonify({"error": file_content}), 400

        use_rag = request.form.get("rag", "true").lower() == "true"
        if use_rag:
            gpt_response = da.analyze_with_gpt_rag_mix(file_content, instruction)
        else:
            gpt_response = da.analyze_with_gpt(file_content, instruction)

        match = re.search(r"\{[\s\S]*\}", gpt_response)
        if not match:
            return jsonify({"error": "AI 回傳不是 JSON", "raw": gpt_response}), 502

        json_text = match.group(0)
        result_json = json.loads(json_text)

        import re as _re

        cert_hours_matches = _re.findall(
            r"認證?\s*時數\s*([0-9]{1,3})\s*小時", file_content
        )
        cert_hours = [int(h) for h in cert_hours_matches]

        read_minutes_matches = _re.findall(
            r"閱讀\s*時數\s*([0-9]{1,4})\s*分鐘", file_content
        )
        read_minutes = [int(m) for m in read_minutes_matches]

        has_exam_any = bool(_re.search(r"測驗\s*成績\s*\d+\s*分", file_content))

        if cert_hours:
            total_hours = sum(cert_hours)
        elif read_minutes:
            total_hours = round(sum(read_minutes) / 60)
        else:
            total_hours = 0

        has_higher = bool(_re.search(r"大專院校|大專生|大學生|技專校院", file_content))
        only_k12 = (not has_higher) and bool(
            _re.search(r"國[高中]|中小學", file_content)
        )
        audience_ok = has_higher or (not only_k12)

        years = _re.findall(r"(20\d{2})", file_content)
        period_ok = any(int(y) >= 2025 for y in years)

        if result_json.get("isPassed") is False:
            or_feedback = (result_json.get("aiFeedback") or "").strip()
            if total_hours >= 12 and audience_ok and has_exam_any and period_ok:
                result_json["isPassed"] = True
                reasons_text = "通過：" + "；".join(["總時數符合", "適用對象符合", "有測驗成績", "開課期間符合"])
                result_json["aiFeedback"] = or_feedback + "\n" + reasons_text

        if result_json.get("isPassed") is False:
            reasons = []
            if total_hours < 12:
                reasons.append(
                    f"總時數不足（依『認證時數/閱讀時數』擷取到 {total_hours} 小時）"
                )
            if not audience_ok:
                reasons.append("適用對象僅見國高中/中小學")
            if not has_exam_any:
                reasons.append("未找到測驗成績")
            if not period_ok:
                reasons.append("未找到符合起始年的開課期間")
            if reasons:
                orig_feedback = (result_json.get("aiFeedback") or "").strip()
                reasons_text = "未通過：" + "；".join(reasons)
                if orig_feedback:
                    result_json["aiFeedback"] = orig_feedback + "\n" + reasons_text
                else:
                    result_json["aiFeedback"] = reasons_text

        now = datetime.now()
        result_json["applyDate"] = now.strftime("%Y-%m-%d")
        result_json["applyTime"] = now.strftime("%H:%M")
        result_json["file_name"] = filename
        result_json["pdf_path"] = f"attachments/{filename}"
        result_json["original_file_name"] = original_filename

        db.insert_scoring_result(result_json)
        return jsonify(result_json), 200
    except json.JSONDecodeError:
        return jsonify({"error": "AI response is not valid JSON."}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@analyze_bp.route("/predict", methods=["POST"])
def predict():
    if "file" not in request.files:
        return jsonify({"ok": False, "msg": "缺少 file"}), 400
    f = request.files["file"]

    pre = preflight_from_upload(f)
    if not pre.ok:
        return (
            jsonify(
                {
                    "ok": False,
                    "stage": "preflight",
                    "reason": pre.reason,
                    "meta": pre.meta,
                }
            ),
            200,
        )

    rag = ask_rag(
        query="從以下文字抽取：課程名稱、時數、起始日期(YYYY-MM-DD)、結束日期(可選)。",
        context=pre.text,
        top_k=5,
        force_citations=True,
    )

    fields = rag.get("fields", {})
    for k, v in fields.items():
        rscore = float(v.get("retrieval_score", 0.0) or 0.0)
        if rscore < RETRIEVAL_SIM_THRESHOLD:
            v["abstain"] = True
    rag["fields"] = fields

    pred = post_validate(rag)
    pred = overall_business_rules(pred)

    return (
        jsonify(
            {
                "ok": True,
                "preflight_meta": pre.meta,
                "model_ver": rag.get("model_ver", "unknown"),
                "rules_ver": "local@1.0.0",
                "fields": pred["fields"],
                "overall_pass": pred["overall_pass"],
                "overall_reasons": pred["overall_reasons"],
            }
        ),
        200,
    )
