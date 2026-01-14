import os

from flask import Blueprint, jsonify, request
from werkzeug.security import generate_password_hash

from ..db import dbStoring as db


departments_bp = Blueprint("departments", __name__, url_prefix="/api/departments")


def _ok(data=None, **kw):
    resp = {"ok": True}
    if data is not None:
        resp["data"] = data
    resp.update(kw)
    return jsonify(resp)


def _err(msg, code=400):
    return jsonify({"ok": False, "error": msg}), code


@departments_bp.post("/bulk_create")
def api_departments_bulk_create():
    """
    建立/更新單位帳號（批次）
    """
    payload = request.get_json(silent=True)
    if not payload:
        return _err("缺少 JSON")
    items = payload.get("items") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        return _err("格式錯誤，應為陣列")

    default_pwd = os.environ.get("DEPT_DEFAULT_PASSWORD", "12345678")
    success = 0
    errors = []
    for idx, rec in enumerate(items):
        unit_no = rec.get("unit_no")
        unit_name = (rec.get("unit_name") or "").strip()
        account = (rec.get("account") or "").strip()
        pwd = rec.get("password") or default_pwd
        if unit_no is None or not unit_name or not account:
            errors.append(f"第 {idx} 筆缺少必填欄位 unit_no/unit_name/account")
            continue
        try:
            unit_no_int = int(unit_no)
        except Exception:
            errors.append(f"第 {idx} 筆 unit_no 需為數字：{unit_no}")
            continue
        try:
            pwd_hash = generate_password_hash(pwd)
            db.create_department(unit_no_int, unit_name, account, pwd_hash)
            success += 1
        except Exception as e:
            errors.append(f"第 {idx} 筆寫入失敗：{e}")

    return _ok({"inserted_or_updated": success, "errors": errors})
