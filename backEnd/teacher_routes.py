# teacher_routes.py
from flask import Blueprint

# 目前先保留一個空的 Blueprint，將來如果真的需要
# 後端處理教師相關 API，再從這裡擴充就好。
teacher_bp = Blueprint("teacher", __name__)
