# API
from flask import Flask, request, jsonify, session
from flask_cors import CORS
import secrets
from werkzeug.security import generate_password_hash, check_password_hash

# file saving
# from werkzeug.utils import secure_filename
import re

# file processing
import os
import json

# AI
import openai
from datetime import datetime

# Import custom modules
import dataAnalyze as da
import dbStoring as db
from guardrails import (
    preflight_from_upload,
    post_validate,
    overall_business_rules,
    RETRIEVAL_SIM_THRESHOLD,
)
from rag_utils import ask_rag
from teacher_routes import teacher_bp


# Initialize the Flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", secrets.token_hex(16))
CORS(app, supports_credentials=True)  # Enable CORS for all routes
db.init_db()
db.init_users_table()

app.register_blueprint(teacher_bp)
print(f"[DB] Using SQLite at: {db.DB_NAME}")


@app.route("/", methods=["GET"])
def hello():
    return "Hello World"


# Config OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")
print(f"OpenAI API Key: {openai.api_key}")  # Debugging line to check if the key is set
if not openai.api_key:
    raise ValueError("Error: OPENAI_API_KEY environment variable is not set!")
conversation_history = []


# 主要要call的API
@app.route("/python-api/analyzeApplication", methods=["POST"])
def generate_application_feedback():
    def sanitize_chinese_filename(filename):
        name, ext = os.path.splitext(filename)
        name = re.sub(r"[^\u4e00-\u9fff\w\-]+", "_", name)
        name = name.strip("_") or "uploaded"
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"{name}_{timestamp}{ext}"

    # Inside your route:
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded."}), 400

    instruction = request.form.get("instruction", "")

    courses = request.form.getlist("courses")
    print("收到課程列表：", courses)

    uploaded_file = request.files["file"]
    original_filename = uploaded_file.filename
    filename = sanitize_chinese_filename(original_filename)

    # 儲存到attachments資料夾
    attachments_dir = os.path.join(os.path.dirname(__file__), "attachments")
    os.makedirs(attachments_dir, exist_ok=True)
    saved_file_path = os.path.join(attachments_dir, filename)
    uploaded_file.save(saved_file_path)

    try:
        file_content = da.extract_file_content(saved_file_path)
        print(file_content)
        if file_content.startswith("Error") or file_content.startswith("Unsupported"):
            return jsonify({"error": file_content}), 400

        # 讓GPT產生審核結果
        # gpt_response = da.analyze_with_gpt(file_content, instruction)
        # 取得是否使用 RAG 模式
        use_rag = request.form.get("rag", "true").lower() == "true"

        if use_rag:
            gpt_response = da.analyze_with_gpt_rag_mix(file_content, instruction)
        else:
            gpt_response = da.analyze_with_gpt(file_content, instruction)

        match = re.search(r"\{[\s\S]*\}", gpt_response)
        if not match:
            return jsonify({"error": "AI 回傳不是 JSON", "raw": gpt_response}), 502

        json_text = match.group(0)
        result_json = json.loads(json_text)

        # ---- 後端複核與兜底：嚴格區分「分(分數)」與「分鐘」 ----
        import re as _re

        # 1) 先抓「認證時數 X 小時」
        cert_hours_matches = _re.findall(
            r"認證?\s*時數\s*([0-9]{1,3})\s*小時", file_content
        )
        cert_hours = [int(h) for h in cert_hours_matches]

        # 2) 沒有認證時數時，改抓「閱讀時數 Y 分鐘」→ 換算小時（四捨五入；也可改成 math.ceil ）
        read_minutes_matches = _re.findall(
            r"閱讀\s*時數\s*([0-9]{1,4})\s*分鐘", file_content
        )
        read_minutes = [int(m) for m in read_minutes_matches]

        # 3) 絕對不要把「測驗成績 Z 分」當分鐘（我們根本不會從「測驗成績」抓分鐘）
        # has_exam_any 只用來判斷是否有考核
        has_exam_any = bool(_re.search(r"測驗\s*成績\s*\d+\s*分", file_content))

        # 4) 匯總小時：有「認證時數」就用認證時數；沒有才用閱讀分鐘換算
        if cert_hours:
            total_hours = sum(cert_hours)
        elif read_minutes:
            total_hours = round(
                sum(read_minutes) / 60
            )  # 144 分 → 2.4h → 2（可改 math.ceil 成 3）
        else:
            total_hours = 0

        # 5) 適用對象：同時含大專 → OK；僅國高中/中小學 → NG
        has_higher = bool(_re.search(r"大專院校|大專生|大學生|技專校院", file_content))
        only_k12 = (not has_higher) and bool(
            _re.search(r"國[高中]|中小學", file_content)
        )
        audience_ok = has_higher or (not only_k12)

        # 6) 開課期間：文件中出現年份 ≥ 2025 視為符合「起始年限制」
        years = _re.findall(r"(20\d{2})", file_content)
        period_ok = any(int(y) >= 2025 for y in years)

        # 7) 若 GPT 判 fail 但複核合格 → 覆寫為通過
        if result_json.get("isPassed") is False:
            if total_hours >= 12 and audience_ok and has_exam_any and period_ok:
                result_json["isPassed"] = True
                result_json["aiFeedback"] = (
                    "通過：複核結果顯示總時數達標，含測驗成績，且適用對象包含大專院校且開課期間符合。"
                )

        # 8) 若仍不通過，補強更精確原因（避免『籠統句』）
        if result_json.get("isPassed") is False:
            reasons = []
            if total_hours < 12:
                reasons.append(
                    f"總時數不足（依『認證時數/閱讀時數』擷取到 {total_hours} 小時）"
                )
            if not audience_ok:
                reasons.append(
                    "適用對象僅見國高中/中小學"
                )
            if not has_exam_any:
                reasons.append(
                    "未找到測驗成績"
                )
            if not period_ok:
                reasons.append(
                    "未找到符合起始年的開課期間"
                )
            if reasons:
                result_json["aiFeedback"] = "未通過：" + "；".join(reasons)

        # print(f"GPT Response: {gpt_response}")  # Debug

        # 將json字串轉成json
        # result_json 已在前面從 json_text 解析完成，避免再次從 gpt_response 重新解析而覆寫

        # 將正確的系統時間輸入json
        now = datetime.now()
        result_json["applyDate"] = now.strftime("%Y-%m-%d")
        result_json["applyTime"] = now.strftime("%H:%M")
        result_json["file_name"] = filename
        result_json["pdf_path"] = f"attachments/{filename}"
        # Optional: for debugging / traceability (not stored unless DB has this column)
        result_json["original_file_name"] = original_filename

        # Save to DB
        db.insert_scoring_result(result_json)

        # Return JSON to frontend
        return jsonify(result_json), 200
    except json.JSONDecodeError:
        return jsonify({"error": "AI response is not valid JSON."}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/label/next", methods=["GET"])
def api_get_next_label():
    """
    取得一筆「尚未被標記」的 history 記錄，
    回傳給前端顯示在標記頁面上。
    """
    row = db.get_next_unlabeled_history()
    if row is None:
        # 沒有待標記資料
        return jsonify({"message": "no_pending_task"}), 200

    resp = {
        "applicantStdn": row["applicantStdn"],
        "applicantNo": row["applicantNo"],
        "applicantName": row["applicantName"],
        "applyDate": row["applyDate"],
        "applyTime": row["applyTime"],
        # 把 AI 的結果包在 aiResult 裡，前端比較好處理
        "aiResult": {
            "isPassed": row["isPassed"],
            "aiFeedback": row["aiFeedback"],
        },
    }
    return jsonify(resp), 200


@app.route("/api/label/submit", methods=["POST"])
def api_submit_label():
    """
    接收前端送來的標記結果，寫入 history_labels。
    期待的 JSON 例如：
    {
      "applicantStdn": "A123456789",
      "applicantNo": 1,
      "labelIsCorrect": true,
      "correctedIsPassed": true,
      "correctedFeedback": "修正後意見",
      "reviewer": "teacherA",
      "reviewComment": "哪裡錯、為什麼錯"
    }
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


@app.route("/predict", methods=["POST"])
def predict():
    """
    multipart/form-data: file=<PDF 或影像>
    回傳：欄位級 JSON（含 abstain 與 overall_pass）
    """
    if "file" not in request.files:
        return jsonify({"ok": False, "msg": "缺少 file"}), 400
    f = request.files["file"]

    # 1) 上游保險絲：抽文字 + OCR 品質
    pre = preflight_from_upload(f)
    if not pre.ok:
        return (
            jsonify(
                {
                    "ok": False,
                    "stage": "preflight",
                    "reason": pre.reason,
                    "meta": pre.meta,
                }
            ),
            200,
        )

    # 2) 中游保險絲：RAG 需強制引用；檢索分數不夠就拒答
    #    你可以在 ask_rag 裡面強化 prompt：每欄位回傳 {value, confidence, evidence:{chunk_id,offset}, retrieval_score, abstain}
    rag = ask_rag(
        query="從以下文字抽取：課程名稱、時數、起始日期(YYYY-MM-DD)、結束日期(可選)。",
        context=pre.text,
        top_k=5,
        force_citations=True,
    )

    # defensive：若某欄位 retrieval_score < 門檻，標記 abstain
    fields = rag.get("fields", {})
    for k, v in fields.items():
        rscore = float(v.get("retrieval_score", 0.0) or 0.0)
        if rscore < RETRIEVAL_SIM_THRESHOLD:
            v["abstain"] = True
    rag["fields"] = fields

    # 3) 下游保險絲：欄位級門檻＆正則與總體規則
    pred = post_validate(rag)
    pred = overall_business_rules(pred)

    return (
        jsonify(
            {
                "ok": True,
                "preflight_meta": pre.meta,
                "model_ver": rag.get("model_ver", "unknown"),
                "rules_ver": "local@1.0.0",
                "fields": pred["fields"],
                "overall_pass": pred["overall_pass"],
                "overall_reasons": pred["overall_reasons"],
            }
        ),
        200,
    )


def ok(data=None, **kw):
    resp = {"ok": True}
    if data is not None:
        resp["data"] = data
    resp.update(kw)
    return jsonify(resp)


def err(msg, code=400):
    return jsonify({"ok": False, "error": msg}), code


@app.route("/api/auth/register", methods=["POST"])
def api_register():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip()
    name = (payload.get("name") or "").strip()
    password = payload.get("password") or ""
    if not email or not name or not password:
        return err("缺少 email/name/password")
    try:
        uid = db.create_user(email, name, generate_password_hash(password))
        return ok({"message": "註冊成功，請登入", "user_id": uid})
    except Exception as e:
        return err(f"Email 已存在或資料庫錯誤: {str(e)}")


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip()
    password = payload.get("password") or ""
    row = db.get_user_by_email(email)
    if not row or not check_password_hash(row[3], password):
        return err("帳號或密碼錯誤", 401)
    session.clear()
    session["uid"] = row[0]
    session["role"] = row[4]
    return ok({"user": {"id": row[0], "email": row[1], "name": row[2], "role": row[4]}})


@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    session.clear()
    return ok({"message": "已登出"})


@app.route("/api/auth/me", methods=["GET"])
def api_me():
    if "uid" not in session:
        return err("未登入", 401)
    return ok({"user": {"id": session["uid"], "role": session["role"]}})


# Run the app on localhost
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
