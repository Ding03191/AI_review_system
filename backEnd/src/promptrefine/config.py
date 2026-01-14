import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
    MAX_UPLOAD_SIZE = int(os.environ.get("MAX_UPLOAD_SIZE", 10 * 1024 * 1024))
    ALLOWED_EXTENSIONS = {"pdf", "doc", "docx"}
    DEPT_DEFAULT_PASSWORD = os.environ.get("DEPT_DEFAULT_PASSWORD", "12345678")
