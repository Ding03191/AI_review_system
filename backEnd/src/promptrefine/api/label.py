from flask import Blueprint, jsonify, request

from ..db import dbStoring as db


label_bp = Blueprint("label", __name__, url_prefix="/api/label")


@label_bp.get("/next")
def api_get_next_label():
    """
    取得一筆「尚未被標記」的 history 記錄，
    回傳給前端顯示在標記頁面上。
    """
    row = db.get_next_unlabeled_history()
    if row is None:
        return jsonify({"message": "no_pending_task"}), 200

    resp = {
        "applicantStdn": row["applicantStdn"],
        "applicantNo": row["applicantNo"],
        "applicantName": row["applicantName"],
        "applyDate": row["applyDate"],
        "applyTime": row["applyTime"],
        "aiResult": {
            "isPassed": row["isPassed"],
            "aiFeedback": row["aiFeedback"],
        },
    }
    return jsonify(resp), 200


@label_bp.post("/submit")
def api_submit_label():
    """
    接收前端送來的標記結果，寫入 history_labels。
    """
    data = request.get_json(force=True)

    label_data = {
        "applicantStdn": data["applicantStdn"],
        "applicantNo": data["applicantNo"],
        "labelIsCorrect": data.get("labelIsCorrect", False),
        "correctedIsPassed": data.get("correctedIsPassed"),
        "correctedFeedback": data.get("correctedFeedback"),
        "reviewer": data.get("reviewer", "teacher"),
        "reviewComment": data.get("reviewComment", ""),
    }

    db.insert_label_result(label_data)
    return jsonify({"status": "ok"}), 200
