import sqlite3
import json
import os

DB_PATH = "scoringHistory.sqlite"       # 你的 SQLite 檔名
JSON_FILE = "labeled_result.json"       # 第三方回傳的 JSON 檔名


def _resolve_db_path():
    base_dir = os.path.dirname(__file__)
    legacy = os.path.join(base_dir, "scoringHistory.sqlite")
    default = os.path.join(base_dir, "db", "scoringHistory.sqlite")
    return os.environ.get("DB_PATH") or (default if os.path.exists(default) else legacy)


DB_PATH = _resolve_db_path()
TABLE_HISTORY = "history"
TABLE_LABELS = "history_labels"


def import_labeled_result():
    # 1. 檢查檔案存在
    if not os.path.exists(JSON_FILE):
        print(f"❌ 找不到 JSON 檔案：{JSON_FILE}")
        return

    # 2. 讀取 JSON
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        records = json.load(f)

    if not isinstance(records, list):
        print("❌ JSON 格式錯誤：最外層應該是陣列 []")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    inserted = 0
    skipped = 0

    for item in records:
        applicantStdn = item.get("applicantStdn")
        applicantNo = item.get("applicantNo")

        human_is_passed = item.get("human_is_passed")  # "pass" / "fail"
        human_reason = (item.get("human_reason") or "").strip()
        reviewer_name = (item.get("reviewer_name") or "").strip()
        review_comment = (item.get("review_comment") or "").strip()

        # 必填欄位檢查
        if not applicantStdn or applicantNo is None:
            print("⚠ 略過一筆：缺少 applicantStdn 或 applicantNo")
            skipped += 1
            continue

        if human_is_passed not in ("pass", "fail"):
            print(f"⚠ 略過 {applicantStdn}-{applicantNo}：human_is_passed 不合法（{human_is_passed}）")
            skipped += 1
            continue

        # 3. 讀 history 看 AI 當時判定 isPassed
        cur.execute(
            f"SELECT isPassed, aiFeedback FROM {TABLE_HISTORY} "
            "WHERE applicantStdn = ? AND applicantNo = ?",
            (applicantStdn, applicantNo),
        )
        row = cur.fetchone()
        if not row:
            print(f"⚠ 在 history 找不到對應紀錄：{applicantStdn}-{applicantNo}")
            skipped += 1
            continue

        ai_is_passed_db = row["isPassed"]  # 0 / 1 或 True / False

        # 4. 人工結果轉成 boolean
        human_pass_bool = 1 if human_is_passed == "pass" else 0

        # 5. 判斷 AI 是否判對
        label_is_correct = 1 if ai_is_passed_db == human_pass_bool else 0

        # 6. 先刪掉舊的標記（避免重複）
        cur.execute(
            f"DELETE FROM {TABLE_LABELS} "
            "WHERE applicantStdn = ? AND applicantNo = ?",
            (applicantStdn, applicantNo),
        )

        # 7. 插入新的標記資料
        cur.execute(
            f"""
            INSERT INTO {TABLE_LABELS} (
                applicantStdn,
                applicantNo,
                labelIsCorrect,
                correctedIsPassed,
                correctedFeedback,
                reviewer,
                reviewComment
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                applicantStdn,
                applicantNo,
                label_is_correct,
                human_pass_bool,
                human_reason,
                reviewer_name,
                review_comment,
            ),
        )

        inserted += 1

    conn.commit()
    conn.close()

    print("========================================")
    print(f"✅ 匯入完成：成功寫入 {inserted} 筆")
    print(f"ℹ 略過 {skipped} 筆（格式或對應問題）")
    print("========================================")


if __name__ == "__main__":
    import_labeled_result()
