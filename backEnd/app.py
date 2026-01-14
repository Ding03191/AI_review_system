import os
import sys

from flask import jsonify, request

from promptrefine import create_app
from promptrefine.db import dbStoring as db


BACKEND_DIR = os.path.abspath(os.path.dirname(__file__))
SRC_DIR = os.path.join(BACKEND_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)


app = create_app()


@app.route("/api/query_records", methods=["GET"])
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
