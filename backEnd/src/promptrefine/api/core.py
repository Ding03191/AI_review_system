from flask import Blueprint, jsonify, request

from ..db import dbStoring as db


core_bp = Blueprint("core", __name__)


@core_bp.route("/", methods=["GET"])
def hello():
    return "Hello World"


@core_bp.route("/api/query_records", methods=["GET"])
def query_records():
    apply_date = request.args.get("date") or request.args.get("applyDate")
    if not apply_date:
        payload = request.get_json(silent=True) or {}
        apply_date = payload.get("date") or payload.get("applyDate")
    if not apply_date:
        return jsonify({"error": "Missing required date parameter."}), 400

    records = db.fetch_records_by_date(apply_date)
    total = len(records)
    passed = sum(1 for record in records if record.get("isPassed"))
    failed = total - passed
    return (
        jsonify(
            {
                "date": apply_date,
                "total": total,
                "passed": passed,
                "failed": failed,
                "records": records,
            }
        ),
        200,
    )
