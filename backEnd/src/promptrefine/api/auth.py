import os

from flask import Blueprint, jsonify, request, session, redirect, url_for, current_app
from authlib.integrations.flask_client import OAuth
from ..services.auth_service import create_user, get_user_by_email, get_user_by_id, verify_password


auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")
oauth = OAuth()


def init_oauth(app):
    oauth.init_app(app)
    client_id = app.config.get("GOOGLE_CLIENT_ID")
    client_secret = app.config.get("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        return
    oauth.register(
        name="google",
        client_id=client_id,
        client_secret=client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )


def json_ok(data=None, **kw):
    resp = {"ok": True}
    if data is not None:
        resp["data"] = data
    resp.update(kw)
    return jsonify(resp)


def json_err(msg, code=400):
    return jsonify({"ok": False, "error": msg}), code


def _admin_email_set():
    raw = current_app.config.get("ADMIN_EMAILS") or ""
    return {item.strip().lower() for item in raw.split(',') if item.strip()}


def _frontend_redirect(default_path="review.html"):
    base = (current_app.config.get("FRONTEND_BASE_URL") or "").rstrip('/')
    if base:
        return f"{base}/{default_path}"
    return default_path


@auth_bp.post("/register")
def register():
    data = request.json or {}
    email = (data.get("studentId") or data.get("email") or "").strip().lower()
    name = data.get("name", "").strip()
    password = data.get("password", "")
    if not email or not name or not password:
        return json_err("Missing required fields")
    try:
        create_user(email, name, password)
    except Exception:
        return json_err("Email already exists or invalid")
    return json_ok({"message": "Registered"})


@auth_bp.post("/login")
def login():
    data = request.json or {}
    email = (data.get("studentId") or data.get("email") or "").strip().lower()
    password = data.get("password", "")
    row = get_user_by_email(email)
    if not verify_password(row, password):
        return json_err("Invalid credentials", 401)
    role = row[4]
    if role == "applicant" and email in _admin_email_set():
        role = "teacher"
    session.clear()
    session["uid"] = row[0]
    session["role"] = role
    return json_ok({"user": {"id": row[0], "studentId": row[1], "name": row[2], "role": role}})


@auth_bp.get("/google/login")
def google_login():
    client = oauth.create_client('google')
    if not client:
        return json_err("Google OAuth not configured", 500)
    redirect_uri = current_app.config.get("GOOGLE_REDIRECT_URI")
    if not redirect_uri:
        redirect_uri = url_for("auth.google_callback", _external=True)
    next_url = (request.args.get("next") or "").strip()
    if next_url:
        session["google_next"] = next_url
    return client.authorize_redirect(redirect_uri)


@auth_bp.get("/google/callback")
def google_callback():
    client = oauth.create_client('google')
    if not client:
        return json_err("Google OAuth not configured", 500)
    token = client.authorize_access_token()
    userinfo = client.parse_id_token(token)
    email = (userinfo.get("email") or "").strip().lower()
    name = (userinfo.get("name") or "").strip() or email
    if not email:
        return json_err("Missing Google account info", 400)

    row = get_user_by_email(email)
    if not row:
        role = "teacher" if email in _admin_email_set() else "applicant"
        temp_password = os.urandom(16).hex()
        create_user(email, name, temp_password, role=role)
        row = get_user_by_email(email)

    session.clear()
    session["uid"] = row[0]
    session["role"] = row[4]

    next_url = session.pop("google_next", None) or _frontend_redirect()
    return redirect(next_url)


@auth_bp.post("/logout")
def logout():
    session.clear()
    return json_ok({"message": "Logged out"})


@auth_bp.get("/me")
def me():
    uid = session.get("uid")
    role = session.get("role")
    if not uid or not role:
        return json_err("Not authenticated", 401)
    row = get_user_by_id(uid)
    if not row:
        session.clear()
        return json_err("Not authenticated", 401)
    return json_ok({"user": {"id": row[0], "studentId": row[1], "name": row[2], "role": role}})


