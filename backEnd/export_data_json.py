import sqlite3
import json
import os
import shutil

DB_PATH = "scoringHistory.sqlite"   # 你的 SQLite 檔案


def _resolve_db_path():
    base_dir = os.path.dirname(__file__)
    legacy = os.path.join(base_dir, "scoringHistory.sqlite")
    default = os.path.join(base_dir, "db", "scoringHistory.sqlite")
    return os.environ.get("DB_PATH") or (default if os.path.exists(default) else legacy)


DB_PATH = _resolve_db_path()
OUTPUT_DIR = "offline_label_pkg"


def export_data_json():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    files_dir = os.path.join(OUTPUT_DIR, "files")
    os.makedirs(files_dir, exist_ok=True)

    base_dir = os.path.dirname(__file__)
    attachments_dir = os.path.join(base_dir, "attachments")

    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    try:
        cur.execute("PRAGMA busy_timeout = 5000")
    except Exception:
        pass

    # Ensure new columns exist even if DB was created before schema update.
    cols = {r[1] for r in cur.execute("PRAGMA table_info(history)").fetchall()}
    if "file_name" not in cols:
        cur.execute("ALTER TABLE history ADD COLUMN file_name TEXT")
    if "pdf_path" not in cols:
        cur.execute("ALTER TABLE history ADD COLUMN pdf_path TEXT")
    if "course_name" not in cols:
        cur.execute("ALTER TABLE history ADD COLUMN course_name TEXT")
    conn.commit()

    # 依照你現在的 history 欄位來 SELECT
    cur.execute("""
        SELECT h.applicantStdn, h.applicantNo, h.applicantName,
               h.course_name, h.file_name, h.pdf_path,
               h.isPassed, h.aiFeedback, h.applyDate, h.applyTime
        FROM history AS h
        LEFT JOIN history_labels AS l
          ON h.applicantStdn = l.applicantStdn
         AND h.applicantNo = l.applicantNo
        WHERE l.id IS NULL
    """)

    rows = cur.fetchall()
    data = []

    for row in rows:
        stdn = row["applicantStdn"]
        no = row["applicantNo"]
        name = row["applicantName"]
        ai_pass = row["isPassed"]          # 0 / 1
        ai_feedback = row["aiFeedback"]
        apply_date = row["applyDate"]
        apply_time = row["applyTime"]
        course_name = (row["course_name"] or "").strip()

        # 目前先沒有確定 PDF 檔名 → 先放空字串
        # 之後你知道檔名規則，我們再把這裡改掉就好
        file_name = (row["file_name"] or "").strip()
        pdf_path = ""

        # fallback: use pdf_path column to derive file name if missing
        if (not file_name) and row["pdf_path"]:
            file_name = os.path.basename(row["pdf_path"])

        # fallback: use applicantStdn.pdf if still empty
        if (not file_name) and stdn:
            candidate = f"{stdn}.pdf"
            if os.path.exists(os.path.join(attachments_dir, candidate)):
                file_name = candidate
            else:
                # fallback: applicantStdn_<anything>.pdf (take latest by mtime)
                pattern = f"{stdn}_"
                cand_files = [
                    f for f in os.listdir(attachments_dir)
                    if f.lower().startswith(pattern.lower()) and f.lower().endswith(".pdf")
                ]
                if cand_files:
                    cand_files.sort(key=lambda n: os.path.getmtime(os.path.join(attachments_dir, n)), reverse=True)
                    file_name = cand_files[0]

        if file_name:
            src_pdf = os.path.join(attachments_dir, file_name)
            dst_pdf = os.path.join(files_dir, file_name)
            if os.path.exists(src_pdf):
                shutil.copy2(src_pdf, dst_pdf)
                pdf_path = f"files/{file_name}"
            else:
                # if source missing, leave pdf_path empty so前端不會點到 404
                pdf_path = ""

        data.append({
            "applicantStdn": stdn,
            "applicantNo": no,
            "applicantName": name,
            "file_name": file_name,
            "pdf_path": pdf_path,
            "ai_is_passed": bool(ai_pass),
            "ai_feedback": ai_feedback,
            "applyDate": apply_date,
            "applyTime": apply_time,
            # 先留給第三方看的補充欄位（之後可用）
            "course_name": course_name,
            "hours": "",
            "score": ""
        })

    conn.close()

    out_path = os.path.join(OUTPUT_DIR, "data.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ 已成功匯出 {len(data)} 筆到 {out_path}")
    print("👉 之後把 offline_label_tool.html 放進同資料夾，就可以用來載入這個 data.json 標記。")


if __name__ == "__main__":
    export_data_json()
