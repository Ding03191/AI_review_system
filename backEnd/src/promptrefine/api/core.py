import json
import os
from datetime import datetime
from io import BytesIO

from flask import Blueprint, jsonify, request, current_app, send_from_directory, session, send_file
from openpyxl import Workbook
from openai import OpenAI

from ..db import dbStoring as db


core_bp = Blueprint("core", __name__)

_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_ATTACHMENTS_DIR = os.path.join(_BACKEND_DIR, "attachments")


def _require_teacher():
    role = session.get("role")
    if not role or role == "applicant":
        return jsonify({"error": "Permission denied."}), 403
    return None


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


def _normalize_filter_dict(payload: dict | None):
    payload = payload or {}

    def _clean(value):
        if value is None:
            return None
        if isinstance(value, str):
            value = value.strip()
        return value or None

    data = {
        "date": _clean(payload.get("date") or payload.get("applyDate")),
        "date_from": _clean(payload.get("date_from") or payload.get("dateFrom")),
        "date_to": _clean(payload.get("date_to") or payload.get("dateTo")),
        "time": _clean(payload.get("time") or payload.get("applyTime")),
        "student_id": _clean(payload.get("student_id") or payload.get("studentId") or payload.get("applicantStdn")),
        "name": _clean(payload.get("name") or payload.get("applicantName")),
        "applicant_no": _clean(payload.get("applicant_no") or payload.get("applicantNo")),
        "course_name": _clean(payload.get("course_name") or payload.get("courseName")),
        "is_passed": _clean(payload.get("is_passed") or payload.get("isPassed")),
        "review_status": _clean(payload.get("review_status") or payload.get("reviewStatus")),
        "feedback_keyword": _clean(payload.get("feedback_keyword") or payload.get("feedbackKeyword")),
        "file_keyword": _clean(payload.get("file_keyword") or payload.get("fileKeyword")),
        "limit": payload.get("limit"),
        "offset": payload.get("offset"),
    }
    return data


@core_bp.route("/api/history/search", methods=["GET", "POST"])
def history_search():
    payload = {}
    if request.method == "GET":
        payload = request.args.to_dict()
    else:
        payload = request.get_json(silent=True) or {}

    filters = _normalize_filter_dict(payload)
    limit = filters.pop("limit", None) or 200
    offset = filters.pop("offset", None) or 0

    results = db.search_records(filters, limit=limit, offset=offset)
    return jsonify(
        {
            "filters": filters,
            "total": results["total"],
            "passed": results["passed"],
            "failed": results["failed"],
            "records": results["records"],
        }
    ), 200


def _extract_filters_with_ai(question: str):
    api_key = current_app.config.get("OPENAI_API_KEY")
    if not api_key:
        return {}

    today = datetime.now().strftime("%Y-%m-%d")
    system_prompt = (
        "You are a strict JSON extractor. "
        "Return JSON only, no markdown. "
        "Extract search filters from the user question. "
        "If unknown, use null. "
        "Date format must be YYYY-MM-DD. "
        "Keys: date, date_from, date_to, student_id, name, applicant_no, "
        "course_name, is_passed, feedback_keyword, file_keyword, limit."
    )
    user_prompt = (
        f"Today is {today}.\n"
        f"Question: {question}\n"
        "Return JSON with the defined keys."
    )
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.0,
    )
    content = (resp.choices[0].message.content or "").strip()
    parsed = _parse_ai_json(content) or {}
    if not isinstance(parsed, dict):
        return {}
    return parsed


def _answer_with_ai(question: str, records: list, summary: dict):
    api_key = current_app.config.get("OPENAI_API_KEY")
    if not api_key:
        return "OPENAI_API_KEY not set."

    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    client = OpenAI(api_key=api_key)
    system_prompt = (
        "You are a helpful assistant. Answer in Traditional Chinese. "
        "Only use the provided records. "
        "If no records, say there are no matching results. "
        "If the question needs clarification, ask one short follow-up question."
    )
    user_payload = {
        "question": question,
        "summary": summary,
        "records": records,
    }
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
        temperature=0.2,
    )
    return (resp.choices[0].message.content or "").strip()


@core_bp.route("/api/history/ask", methods=["POST"])
def history_ask():
    payload = request.get_json(silent=True) or {}
    question = (payload.get("question") or "").strip()
    if not question:
        return jsonify({"error": "Missing question."}), 400

    scope_filters = _normalize_filter_dict(payload.get("scope") or {})
    extracted = _extract_filters_with_ai(question)
    merged = _normalize_filter_dict(extracted)

    # Scope filters take precedence if provided
    for key, value in scope_filters.items():
        if value is not None and value != "":
            merged[key] = value

    limit = merged.pop("limit", None) or 50
    results = db.search_records(merged, limit=limit, offset=0)
    summary = {
        "total": results["total"],
        "passed": results["passed"],
        "failed": results["failed"],
        "returned": len(results["records"]),
    }

    answer = _answer_with_ai(question, results["records"], summary)
    return jsonify(
        {
            "question": question,
            "filters": merged,
            "summary": summary,
            "answer": answer,
            "records": results["records"],
        }
    ), 200


@core_bp.route("/attachments/<path:filename>", methods=["GET"])
def serve_attachment(filename):
    return send_from_directory(_ATTACHMENTS_DIR, filename, as_attachment=False)


@core_bp.route("/api/labeling/unlabeled", methods=["GET"])
def labeling_unlabeled():
    guard = _require_teacher()
    if guard:
        return guard
    limit = request.args.get("limit", 50)
    offset = request.args.get("offset", 0)
    results = db.fetch_unlabeled_records(limit=limit, offset=offset)
    return jsonify(results), 200


@core_bp.route("/api/labeling/labeled", methods=["GET"])
def labeling_labeled():
    guard = _require_teacher()
    if guard:
        return guard
    limit = request.args.get("limit", 50)
    offset = request.args.get("offset", 0)
    results = db.fetch_labeled_records(limit=limit, offset=offset)
    return jsonify(results), 200


@core_bp.route("/api/labeling/record", methods=["GET"])
def labeling_record():
    guard = _require_teacher()
    if guard:
        return guard
    applicant_stdn = (request.args.get("applicantStdn") or "").strip()
    applicant_no = request.args.get("applicantNo")
    if not applicant_stdn or applicant_no is None:
        return jsonify({"error": "Missing applicantStdn or applicantNo."}), 400

    record = db.get_history_record(applicant_stdn, applicant_no)
    if not record:
        return jsonify({"error": "Record not found."}), 404
    db.mark_reviewing(applicant_stdn, applicant_no)
    label = db.get_latest_label(applicant_stdn, applicant_no)
    record["label"] = label
    return jsonify(record), 200


@core_bp.route("/api/labeling/export_excel", methods=["GET"])
def labeling_export_excel():
    guard = _require_teacher()
    if guard:
        return guard
    results = db.search_records({}, limit=100000, offset=0)
    records = results.get("records", [])

    wb = Workbook()
    ws = wb.active
    ws.title = "reviews"
    headers = [
        "Apply Date",
        "Apply Time",
        "Applicant Name",
        "Student ID",
        "Case No",
        "Course",
        "AI Result",
        "Review Status",
        "Teacher Result",
        "Teacher Feedback",
        "Teacher Table (JSON)",
        "Reviewed At",
    ]
    ws.append(headers)

    for rec in records:
        ws.append(
            [
                rec.get("applyDate") or "",
                rec.get("applyTime") or "",
                rec.get("applicantName") or "",
                rec.get("applicantStdn") or "",
                rec.get("applicantNo") if rec.get("applicantNo") is not None else "",
                rec.get("course_name") or "",
                "PASS" if rec.get("isPassed") else "FAIL",
                rec.get("reviewStatus") or "submitted",
                "PASS" if rec.get("finalIsPassed") is True else ("FAIL" if rec.get("finalIsPassed") is False else ""),
                rec.get("finalFeedback") or "",
                json.dumps(rec.get("finalFeedbackTable") or [], ensure_ascii=False),
                rec.get("reviewedAt") or "",
            ]
        )

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = f"review_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(
        buf,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@core_bp.route("/api/labeling/submit", methods=["POST"])
def labeling_submit():
    guard = _require_teacher()
    if guard:
        return guard
    payload = request.get_json(silent=True) or {}
    applicant_stdn = (payload.get("applicantStdn") or "").strip()
    applicant_no = payload.get("applicantNo")
    reviewer = (payload.get("reviewer") or "").strip()
    review_status = (payload.get("reviewStatus") or "").strip()
    corrected_is_passed = payload.get("correctedIsPassed")
    corrected_feedback = (payload.get("correctedFeedback") or "").strip()
    corrected_feedback_table = payload.get("correctedFeedbackTable") or []
    review_comment = (payload.get("reviewComment") or "").strip()
    selected_regions = payload.get("selectedRegions") or []

    if not applicant_stdn or applicant_no is None:
        return jsonify({"error": "Missing applicantStdn or applicantNo."}), 400
    if review_status not in ("approved", "rejected", "returned"):
        if corrected_is_passed is True:
            review_status = "approved"
        elif corrected_is_passed is False:
            review_status = "rejected"
        else:
            review_status = "returned"
    if reviewer == "":
        reviewer = f"user:{session.get('uid')}" if session.get("uid") else "system"

    record = db.get_history_record(applicant_stdn, applicant_no)
    if not record:
        return jsonify({"error": "Record not found."}), 404

    final_is_passed = None
    if review_status == "approved":
        final_is_passed = True
    elif review_status == "rejected":
        final_is_passed = False
    elif review_status == "returned":
        final_is_passed = None

    label_is_correct = False
    if corrected_is_passed is not None:
        label_is_correct = bool(record.get("isPassed")) == bool(corrected_is_passed)
    db.insert_label_result(
        {
            "applicantStdn": applicant_stdn,
            "applicantNo": applicant_no,
            "labelIsCorrect": label_is_correct,
            "correctedIsPassed": bool(corrected_is_passed),
            "correctedFeedback": corrected_feedback,
            "correctedFeedbackTable": corrected_feedback_table if isinstance(corrected_feedback_table, list) else [],
            "selectedRegions": selected_regions if isinstance(selected_regions, list) else [],
            "reviewer": reviewer,
            "reviewComment": review_comment,
        }
    )
    db.update_review_result(
        applicant_stdn,
        applicant_no,
        review_status,
        final_is_passed,
        corrected_feedback,
        corrected_feedback_table if isinstance(corrected_feedback_table, list) else [],
    )
    return jsonify({"ok": True, "labelIsCorrect": label_is_correct}), 200
