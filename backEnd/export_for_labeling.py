import sqlite3
import json
import os
import shutil

DB_PATH = "scoring.db"          # 換成你的 DB 檔名
ATTACH_DIR = "attachments"      # 現在存 PDF 的資料夾
OUTPUT_DIR = "offline_label_pkg"  # 輸出給第三方的資料夾
FILES_DIR = os.path.join(OUTPUT_DIR, "files")
OUTPUT_JSON = os.path.join(OUTPUT_DIR, "data.json")


def export_for_labeling():
    os.makedirs(FILES_DIR, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 這邊你可以加 WHERE 條件，例如只匯出 AI 判定有問題的
    cur.execute("""
        SELECT id, file_name, course_name, hours, score, ai_is_passed, ai_feedback
        FROM scoringHistory
        -- WHERE need_human_label = 1
    """)

    rows = cur.fetchall()
    data = []

    for row in rows:
        file_name = row["file_name"]

        # 原始 PDF 路徑
        src_pdf = os.path.join(ATTACH_DIR, file_name)

        # 放到給第三方看的 files/ 資料夾
        dst_pdf = os.path.join(FILES_DIR, file_name)

        if os.path.exists(src_pdf):
            shutil.copy2(src_pdf, dst_pdf)
        else:
            print(f"[警告] 找不到檔案：{src_pdf}")

        item = {
            "case_id": f"C{row['id']}",  # 或直接 str(row['id'])
            "file_name": file_name,
            "pdf_path": f"files/{file_name}",  # 給前端開啟用（相對路徑）
            "course_name": row["course_name"],
            "hours": row["hours"],
            "score": row["score"],
            "ai_is_passed": bool(row["ai_is_passed"]),
            "ai_feedback": row["ai_feedback"],
        }
        data.append(item)

    conn.close()

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"匯出完成，共 {len(data)} 筆")
    print(f"  - JSON：{OUTPUT_JSON}")
    print(f"  - PDF：{FILES_DIR}/ 底下")


if __name__ == "__main__":
    export_for_labeling()
