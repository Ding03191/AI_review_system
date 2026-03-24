import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
    MAX_UPLOAD_SIZE = int(os.environ.get("MAX_UPLOAD_SIZE", 10 * 1024 * 1024))
    ALLOWED_EXTENSIONS = {"pdf", "doc", "docx"}
    DEPT_DEFAULT_PASSWORD = os.environ.get("DEPT_DEFAULT_PASSWORD", "12345678")
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI")
    FRONTEND_BASE_URL = os.environ.get("FRONTEND_BASE_URL", "http://127.0.0.1:8082/public")
    ADMIN_EMAILS = os.environ.get("ADMIN_EMAILS", "")
