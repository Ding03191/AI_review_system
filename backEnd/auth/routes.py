from flask import Blueprint, request, jsonify, session
from .model import get_user_by_email, create_user, verify_password


auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


def json_ok(data=None, **kw):
    resp = {"ok": True}
    if data is not None:
        resp["data"] = data
    resp.update(kw)
    return jsonify(resp)


def json_err(msg, code=400):
    return jsonify({"ok": False, "error": msg}), code


@auth_bp.post('/register')
def register():
    conn = request.app_db()  # 由 app.py 提供 db 連線方法，見下節
    data = request.json or {}
    email = data.get('email', '').strip()
    name = data.get('name', '').strip()
    password = data.get('password', '')
    if not email or not name or not password:
        return json_err("缺少必要欄位")
    try:
        create_user(conn, email, name, password)
    except Exception:
        return json_err("Email 已被註冊或資料庫錯誤")
    return json_ok({"message": "註冊成功，請登入"})


@auth_bp.post('/login')
def login():
    conn = request.app_db()
    data = request.json or {}
    email = data.get('email', '').strip()
    password = data.get('password', '')
    row = get_user_by_email(conn, email)
    if not verify_password(row, password):
        return json_err("帳號或密碼錯誤", 401)
    # 簡單 session（同網域部署時可用）；若純前後端分離可改 JWT
    session.clear()
    session['uid'] = row[0]
    session['role'] = row[4]
    return json_ok({"user": {"id": row[0], "email": row[1], "name": row[2], "role": row[4]}})


@auth_bp.post('/logout')
def logout():
    session.clear()
    return json_ok({"message": "已登出"})


@auth_bp.get('/me')
def me():
    if 'uid' not in session:
        return json_err("未登入", 401)
    return json_ok({"user": {"id": session['uid'], "role": session['role']}})
