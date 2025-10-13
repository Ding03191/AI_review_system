# API
from flask import Flask, request, jsonify
from flask_cors import CORS
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


# Initialize the Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
db.init_db()


@app.route('/', methods=['GET'])
def hello():
    return "Hello World"


# Config OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")
print(f"OpenAI API Key: {openai.api_key}")  # Debugging line to check if the key is set
if not openai.api_key:
    raise ValueError("Error: OPENAI_API_KEY environment variable is not set!")
conversation_history = []


# 主要要call的API
@app.route('/python-api/analyzeApplication', methods=['POST'])
def generate_application_feedback():
    def sanitize_chinese_filename(filename):
        name, ext = os.path.splitext(filename)
        name = re.sub(r'[^\u4e00-\u9fff\w\-]+', '_', name)
        name = name.strip('_') or 'uploaded'
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        return f"{name}_{timestamp}{ext}"

    # Inside your route:
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded."}), 400

    instruction = request.form.get('instruction', '')

    uploaded_file = request.files['file']
    filename = sanitize_chinese_filename(uploaded_file.filename)

    # 儲存到attachments資料夾
    attachments_dir = os.path.join(os.path.dirname(__file__), 'attachments')
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

        match = re.search(r'\{.*\}', gpt_response, re.DOTALL)
        if not match:
            raise ValueError("GPT 回傳內容無法解析成 JSON:\n" + gpt_response)

        # print(f"GPT Response: {gpt_response}")  # Debug

        # 將json字串轉成json
        result_json = json.loads(gpt_response)

        # 將正確的系統時間輸入json
        now = datetime.now()
        result_json["applyDate"] = now.strftime("%Y-%m-%d")
        result_json["applyTime"] = now.strftime("%H:%M")

        # Save to DB
        db.insert_scoring_result(result_json)

        # Return JSON to frontend
        return jsonify(result_json), 200
    except json.JSONDecodeError:
        return jsonify({"error": "AI response is not valid JSON."}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Run the app on localhost
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
