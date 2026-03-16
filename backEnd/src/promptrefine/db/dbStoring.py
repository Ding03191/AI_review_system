import json
import os
import shutil
import sqlite3
# from datetime import datetime


_BASE_DIR = os.path.dirname(__file__)
_BACKEND_DIR = os.path.abspath(os.path.join(_BASE_DIR, "..", "..", ".."))
_LEGACY_DB_PATH = os.path.join(_BACKEND_DIR, "scoringHistory.sqlite")
_DEFAULT_DB_PATH = os.path.join(_BACKEND_DIR, "db", "scoringHistory.sqlite")
DB_NAME = os.environ.get("DB_PATH", _DEFAULT_DB_PATH)
TABLE_NAME = 'history'
LABEL_TABLE_NAME = "history_labels"
DEPT_TABLE_NAME = "departments"


def _ensure_db_path():
    os.makedirs(os.path.dirname(DB_NAME), exist_ok=True)
    if DB_NAME != _LEGACY_DB_PATH and (not os.path.exists(DB_NAME)) and os.path.exists(_LEGACY_DB_PATH):
        shutil.copy2(_LEGACY_DB_PATH, DB_NAME)


def _connect():
    _ensure_db_path()
    conn = sqlite3.connect(DB_NAME, timeout=30)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
    except Exception:
        pass
    return conn


# 1. Create the table if it doesn't exist
def init_db():
    conn = _connect()
    c = conn.cursor()
    c.execute(f'''
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            applicantStdn TEXT,
            applicantNo INTEGER,
            applicantName TEXT,
            course_name TEXT,
            file_name TEXT,
            pdf_path TEXT,
            isPassed BOOLEAN,
            aiFeedback TEXT,
            aiFeedbackTable TEXT,
            reviewStatus TEXT DEFAULT 'submitted',
            finalIsPassed BOOLEAN,
            finalFeedback TEXT,
            finalFeedbackTable TEXT,
            reviewedAt TEXT,
            applyDate TEXT,
            applyTime TEXT,
            PRIMARY KEY (applicantStdn, applicantNo)
        )
    ''')
    c.execute(f'''
        CREATE TABLE IF NOT EXISTS {LABEL_TABLE_NAME} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            applicantStdn TEXT NOT NULL,
            applicantNo INTEGER NOT NULL,

            labelIsCorrect INTEGER NOT NULL,     -- 1 = AI 判斷正確, 0 = 判錯
            correctedIsPassed BOOLEAN,           -- 人工修正後的 isPassed
            correctedFeedback TEXT,              -- 人工修正後的 aiFeedback
            selectedRegions TEXT,                -- 手動框選區域(JSON)

            reviewer TEXT,                       -- 標記人，例如 teacherA
            reviewComment TEXT,                  -- 備註
            labeledAt TEXT DEFAULT (datetime('now','localtime')),

            FOREIGN KEY (applicantStdn, applicantNo)
                REFERENCES {TABLE_NAME}(applicantStdn, applicantNo)
        )
    ''')

    c.execute(f'''
        CREATE TABLE IF NOT EXISTS {DEPT_TABLE_NAME} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unit_no INTEGER UNIQUE NOT NULL,
            unit_name TEXT NOT NULL,
            account TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()

    # Backward-compatible schema migration: add columns if old DB already exists.
    existing_cols = {row[1] for row in c.execute(f"PRAGMA table_info({TABLE_NAME})").fetchall()}
    for col, col_type in (
        ("file_name", "TEXT"),
        ("pdf_path", "TEXT"),
        ("course_name", "TEXT"),
        ("aiFeedbackTable", "TEXT"),
        ("reviewStatus", "TEXT"),
        ("finalIsPassed", "BOOLEAN"),
        ("finalFeedback", "TEXT"),
        ("finalFeedbackTable", "TEXT"),
        ("reviewedAt", "TEXT"),
    ):
        if col not in existing_cols:
            c.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN {col} {col_type}")

    existing_label_cols = {row[1] for row in c.execute(f"PRAGMA table_info({LABEL_TABLE_NAME})").fetchall()}
    if "selectedRegions" not in existing_label_cols:
        c.execute(f"ALTER TABLE {LABEL_TABLE_NAME} ADD COLUMN selectedRegions TEXT")
    if "correctedFeedbackTable" not in existing_label_cols:
        c.execute(f"ALTER TABLE {LABEL_TABLE_NAME} ADD COLUMN correctedFeedbackTable TEXT")

    conn.commit()
    conn.close()

# 2. Insert a record


def insert_scoring_result(data):
    conn = _connect()
    c = conn.cursor()

    c.execute(f'''
        INSERT INTO {TABLE_NAME} (
            applicantStdn,
            applicantNo,
            applicantName,
            course_name,
            file_name,
            pdf_path,
            isPassed,
            aiFeedback,
            aiFeedbackTable,
            reviewStatus,
            finalIsPassed,
            finalFeedback,
            finalFeedbackTable,
            reviewedAt,
            applyDate,
            applyTime
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data['applicantStdn'],
        data['applicantNo'],
        data['applicantName'],
        data.get('course_name'),
        data.get('file_name'),
        data.get('pdf_path'),
        int(data['isPassed']),  # Store boolean as 0 or 1
        data['aiFeedback'],
        json.dumps(data.get('aiFeedbackTable') or [], ensure_ascii=False),
        data.get('reviewStatus') or 'submitted',
        data.get('finalIsPassed'),
        data.get('finalFeedback'),
        json.dumps(data.get('finalFeedbackTable') or [], ensure_ascii=False)
        if data.get('finalFeedbackTable') is not None else None,
        data.get('reviewedAt'),
        data['applyDate'],
        data['applyTime']
    ))

    conn.commit()
    conn.close()


def has_history_record(applicant_stdn: str, applicant_no):
    conn = _connect()
    c = conn.cursor()
    row = c.execute(
        f"SELECT 1 FROM {TABLE_NAME} WHERE applicantStdn = ? AND applicantNo = ?",
        (applicant_stdn, applicant_no),
    ).fetchone()
    conn.close()
    return bool(row)

# 3. Optional: Fetch all history


def fetch_all_results():
    conn = _connect()
    c = conn.cursor()
    c.execute(f'SELECT * FROM {TABLE_NAME}')
    results = c.fetchall()
    conn.close()
    return results


def fetch_records_by_date(apply_date: str):
    conn = _connect()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        f"""
        SELECT applicantStdn,
               applicantNo,
               applicantName,
               file_name,
               pdf_path,
               isPassed,
               aiFeedback,
               aiFeedbackTable,
               reviewStatus,
               finalIsPassed,
               finalFeedback,
               finalFeedbackTable,
               reviewedAt,
               applyDate,
               applyTime
        FROM {TABLE_NAME}
        WHERE applyDate = ?
        ORDER BY applyTime
        """,
        (apply_date,),
    )
    rows = c.fetchall()
    conn.close()

    records = []
    for row in rows:
        records.append(
            {
                "applicantStdn": row["applicantStdn"],
                "applicantNo": row["applicantNo"],
                "applicantName": row["applicantName"],
                "file_name": row["file_name"],
                "pdf_path": row["pdf_path"],
                "isPassed": bool(row["isPassed"]),
                "aiFeedback": row["aiFeedback"],
                "aiFeedbackTable": json.loads(row["aiFeedbackTable"]) if row["aiFeedbackTable"] else [],
                "reviewStatus": row["reviewStatus"] or "submitted",
                "finalIsPassed": bool(row["finalIsPassed"]) if row["finalIsPassed"] is not None else None,
                "finalFeedback": row["finalFeedback"],
                "finalFeedbackTable": json.loads(row["finalFeedbackTable"]) if row["finalFeedbackTable"] else [],
                "reviewedAt": row["reviewedAt"],
                "applyDate": row["applyDate"],
                "applyTime": row["applyTime"],
            }
        )
    return records


def search_records(filters: dict | None = None, limit: int = 200, offset: int = 0):
    filters = filters or {}
    limit = max(1, min(int(limit or 200), 500))
    offset = max(0, int(offset or 0))

    def _clean(value):
        if value is None:
            return None
        if isinstance(value, str):
            value = value.strip()
        return value or None

    def _parse_bool(value):
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in ("1", "true", "yes", "y", "pass", "passed", "ok"):
            return True
        if text in ("0", "false", "no", "n", "fail", "failed", "ng"):
            return False
        return None

    where = []
    params = []

    date_exact = _clean(filters.get("date") or filters.get("applyDate"))
    date_from = _clean(filters.get("date_from") or filters.get("dateFrom"))
    date_to = _clean(filters.get("date_to") or filters.get("dateTo"))
    time_exact = _clean(filters.get("time") or filters.get("applyTime"))
    student_id = _clean(filters.get("student_id") or filters.get("studentId") or filters.get("applicantStdn"))
    name = _clean(filters.get("name") or filters.get("applicantName"))
    applicant_no = _clean(filters.get("applicant_no") or filters.get("applicantNo"))
    course_name = _clean(filters.get("course_name") or filters.get("courseName"))
    is_passed = _parse_bool(filters.get("is_passed") or filters.get("isPassed"))
    review_status = _clean(filters.get("review_status") or filters.get("reviewStatus"))
    feedback_keyword = _clean(filters.get("feedback_keyword") or filters.get("feedbackKeyword"))
    file_keyword = _clean(filters.get("file_keyword") or filters.get("fileKeyword"))

    if date_exact:
        where.append("applyDate = ?")
        params.append(date_exact)
    else:
        if date_from:
            where.append("applyDate >= ?")
            params.append(date_from)
        if date_to:
            where.append("applyDate <= ?")
            params.append(date_to)
    if time_exact:
        if "-" in time_exact:
            where.append("applyDate LIKE ?")
            params.append(f"%{time_exact}%")
        else:
            where.append("applyTime LIKE ?")
            params.append(f"%{time_exact}%")
    if student_id:
        where.append("applicantStdn LIKE ?")
        params.append(f"%{student_id}%")
    if name:
        where.append("applicantName LIKE ?")
        params.append(f"%{name}%")
    if applicant_no:
        where.append("applicantNo = ?")
        params.append(applicant_no)
    if course_name:
        where.append("course_name LIKE ?")
        params.append(f"%{course_name}%")
    if is_passed is not None:
        where.append("isPassed = ?")
        params.append(1 if is_passed else 0)
    if review_status:
        where.append("reviewStatus = ?")
        params.append(review_status)
    if feedback_keyword:
        where.append("aiFeedback LIKE ?")
        params.append(f"%{feedback_keyword}%")
    if file_keyword:
        where.append("(file_name LIKE ? OR pdf_path LIKE ?)")
        params.append(f"%{file_keyword}%")
        params.append(f"%{file_keyword}%")

    where_sql = f" WHERE {' AND '.join(where)}" if where else ""

    conn = _connect()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    count = c.execute(
        f"SELECT COUNT(*) FROM {TABLE_NAME}{where_sql}",
        params,
    ).fetchone()[0]

    if where_sql:
        passed_sql = f"SELECT COUNT(*) FROM {TABLE_NAME}{where_sql} AND isPassed = 1"
        passed_params = params
    else:
        passed_sql = f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE isPassed = 1"
        passed_params = []
    passed = c.execute(passed_sql, passed_params).fetchone()[0]
    failed = count - passed

    rows = c.execute(
        f"""
        SELECT applicantStdn,
               applicantNo,
               applicantName,
               course_name,
               file_name,
               pdf_path,
               isPassed,
               aiFeedback,
               aiFeedbackTable,
               reviewStatus,
               finalIsPassed,
               finalFeedback,
               finalFeedbackTable,
               reviewedAt,
               applyDate,
               applyTime
        FROM {TABLE_NAME}
        {where_sql}
        ORDER BY applyDate DESC, applyTime DESC
        LIMIT ? OFFSET ?
        """,
        [*params, limit, offset],
    ).fetchall()
    conn.close()

    records = []
    for row in rows:
        records.append(
            {
                "applicantStdn": row["applicantStdn"],
                "applicantNo": row["applicantNo"],
                "applicantName": row["applicantName"],
                "course_name": row["course_name"],
                "file_name": row["file_name"],
                "pdf_path": row["pdf_path"],
                "isPassed": bool(row["isPassed"]),
                "aiFeedback": row["aiFeedback"],
                "aiFeedbackTable": json.loads(row["aiFeedbackTable"]) if row["aiFeedbackTable"] else [],
                "reviewStatus": row["reviewStatus"] or "submitted",
                "finalIsPassed": bool(row["finalIsPassed"]) if row["finalIsPassed"] is not None else None,
                "finalFeedback": row["finalFeedback"],
                "finalFeedbackTable": json.loads(row["finalFeedbackTable"]) if row["finalFeedbackTable"] else [],
                "reviewedAt": row["reviewedAt"],
                "applyDate": row["applyDate"],
                "applyTime": row["applyTime"],
            }
        )
    return {
        "records": records,
        "total": count,
        "passed": passed,
        "failed": failed,
    }


def get_history_record(applicant_stdn: str, applicant_no):
    conn = _connect()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    row = c.execute(
        f"""
        SELECT applicantStdn,
               applicantNo,
               applicantName,
               course_name,
               file_name,
               pdf_path,
               isPassed,
               aiFeedback,
               aiFeedbackTable,
               reviewStatus,
               finalIsPassed,
               finalFeedback,
               finalFeedbackTable,
               reviewedAt,
               applyDate,
               applyTime
        FROM {TABLE_NAME}
        WHERE applicantStdn = ? AND applicantNo = ?
        """,
        (applicant_stdn, applicant_no),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return {
        "applicantStdn": row["applicantStdn"],
        "applicantNo": row["applicantNo"],
        "applicantName": row["applicantName"],
        "course_name": row["course_name"],
        "file_name": row["file_name"],
        "pdf_path": row["pdf_path"],
        "isPassed": bool(row["isPassed"]),
        "aiFeedback": row["aiFeedback"],
        "aiFeedbackTable": json.loads(row["aiFeedbackTable"]) if row["aiFeedbackTable"] else [],
        "reviewStatus": row["reviewStatus"] or "submitted",
        "finalIsPassed": bool(row["finalIsPassed"]) if row["finalIsPassed"] is not None else None,
        "finalFeedback": row["finalFeedback"],
        "finalFeedbackTable": json.loads(row["finalFeedbackTable"]) if row["finalFeedbackTable"] else [],
        "reviewedAt": row["reviewedAt"],
        "applyDate": row["applyDate"],
        "applyTime": row["applyTime"],
    }


def get_latest_label(applicant_stdn: str, applicant_no):
    conn = _connect()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    row = c.execute(
        f"""
        SELECT id,
               labelIsCorrect,
               correctedIsPassed,
               correctedFeedback,
               correctedFeedbackTable,
               selectedRegions,
               reviewer,
               reviewComment,
               labeledAt
        FROM {LABEL_TABLE_NAME}
        WHERE applicantStdn = ? AND applicantNo = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (applicant_stdn, applicant_no),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return {
        "id": row["id"],
        "labelIsCorrect": bool(row["labelIsCorrect"]),
        "correctedIsPassed": bool(row["correctedIsPassed"]) if row["correctedIsPassed"] is not None else None,
        "correctedFeedback": row["correctedFeedback"],
        "correctedFeedbackTable": json.loads(row["correctedFeedbackTable"]) if row["correctedFeedbackTable"] else [],
        "selectedRegions": json.loads(row["selectedRegions"]) if row["selectedRegions"] else [],
        "reviewer": row["reviewer"],
        "reviewComment": row["reviewComment"],
        "labeledAt": row["labeledAt"],
    }


def mark_reviewing(applicant_stdn: str, applicant_no):
    conn = _connect()
    c = conn.cursor()
    c.execute(
        f"""
        UPDATE {TABLE_NAME}
        SET reviewStatus = 'reviewing'
        WHERE applicantStdn = ? AND applicantNo = ? AND (reviewStatus IS NULL OR reviewStatus = 'submitted')
        """,
        (applicant_stdn, applicant_no),
    )
    conn.commit()
    conn.close()


def update_review_result(
    applicant_stdn: str,
    applicant_no,
    review_status: str,
    final_is_passed,
    final_feedback: str,
    final_feedback_table: list | None,
):
    conn = _connect()
    c = conn.cursor()
    c.execute(
        f"""
        UPDATE {TABLE_NAME}
        SET reviewStatus = ?,
            finalIsPassed = ?,
            finalFeedback = ?,
            finalFeedbackTable = ?,
            reviewedAt = datetime('now','localtime')
        WHERE applicantStdn = ? AND applicantNo = ?
        """,
        (
            review_status,
            None if final_is_passed is None else int(bool(final_is_passed)),
            final_feedback,
            json.dumps(final_feedback_table or [], ensure_ascii=False),
            applicant_stdn,
            applicant_no,
        ),
    )
    conn.commit()
    conn.close()


def fetch_unlabeled_records(limit: int = 50, offset: int = 0):
    limit = max(1, min(int(limit or 50), 200))
    offset = max(0, int(offset or 0))

    conn = _connect()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    total = c.execute(
        f"""
        SELECT COUNT(*)
        FROM {TABLE_NAME} AS h
        LEFT JOIN {LABEL_TABLE_NAME} AS l
          ON h.applicantStdn = l.applicantStdn
         AND h.applicantNo  = l.applicantNo
        WHERE l.id IS NULL
        """
    ).fetchone()[0]

    rows = c.execute(
        f"""
        SELECT h.applicantStdn,
               h.applicantNo,
               h.applicantName,
               h.course_name,
               h.file_name,
               h.pdf_path,
               h.isPassed,
               h.aiFeedback,
               h.aiFeedbackTable,
               h.reviewStatus,
               h.finalIsPassed,
               h.finalFeedback,
               h.finalFeedbackTable,
               h.reviewedAt,
               h.applyDate,
               h.applyTime
        FROM {TABLE_NAME} AS h
        LEFT JOIN {LABEL_TABLE_NAME} AS l
          ON h.applicantStdn = l.applicantStdn
         AND h.applicantNo  = l.applicantNo
        WHERE l.id IS NULL
        ORDER BY h.applyDate DESC, h.applyTime DESC
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    ).fetchall()
    conn.close()

    records = []
    for row in rows:
        records.append(
            {
                "applicantStdn": row["applicantStdn"],
                "applicantNo": row["applicantNo"],
                "applicantName": row["applicantName"],
                "course_name": row["course_name"],
                "file_name": row["file_name"],
                "pdf_path": row["pdf_path"],
                "isPassed": bool(row["isPassed"]),
                "aiFeedback": row["aiFeedback"],
                "aiFeedbackTable": json.loads(row["aiFeedbackTable"]) if row["aiFeedbackTable"] else [],
                "reviewStatus": row["reviewStatus"] or "submitted",
                "finalIsPassed": bool(row["finalIsPassed"]) if row["finalIsPassed"] is not None else None,
                "finalFeedback": row["finalFeedback"],
                "finalFeedbackTable": json.loads(row["finalFeedbackTable"]) if row["finalFeedbackTable"] else [],
                "reviewedAt": row["reviewedAt"],
                "applyDate": row["applyDate"],
                "applyTime": row["applyTime"],
            }
        )

    return {
        "total": total,
        "records": records,
        "limit": limit,
        "offset": offset,
        "returned": len(records),
    }


def fetch_labeled_records(limit: int = 50, offset: int = 0):
    limit = max(1, min(int(limit or 50), 500))
    offset = max(0, int(offset or 0))

    conn = _connect()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    total = c.execute(
        f"""
        SELECT COUNT(*)
        FROM (
            SELECT applicantStdn, applicantNo
            FROM {LABEL_TABLE_NAME}
            GROUP BY applicantStdn, applicantNo
        ) AS x
        """
    ).fetchone()[0]

    rows = c.execute(
        f"""
        SELECT h.applicantStdn,
               h.applicantNo,
               h.applicantName,
               h.course_name,
               h.file_name,
               h.pdf_path,
               h.isPassed,
               h.aiFeedback,
               h.aiFeedbackTable,
               h.reviewStatus,
               h.finalIsPassed,
               h.finalFeedback,
               h.finalFeedbackTable,
               h.reviewedAt,
               h.applyDate,
               h.applyTime,
               l.labelIsCorrect,
               l.correctedIsPassed,
               l.correctedFeedback,
               l.correctedFeedbackTable,
               l.selectedRegions,
               l.reviewer,
               l.reviewComment,
               l.labeledAt
        FROM {TABLE_NAME} AS h
        INNER JOIN (
            SELECT applicantStdn, applicantNo, MAX(id) AS latest_id
            FROM {LABEL_TABLE_NAME}
            GROUP BY applicantStdn, applicantNo
        ) AS latest
          ON h.applicantStdn = latest.applicantStdn
         AND h.applicantNo = latest.applicantNo
        INNER JOIN {LABEL_TABLE_NAME} AS l
          ON l.id = latest.latest_id
        ORDER BY l.labeledAt DESC
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    ).fetchall()
    conn.close()

    records = []
    for row in rows:
        records.append(
            {
                "applicantStdn": row["applicantStdn"],
                "applicantNo": row["applicantNo"],
                "applicantName": row["applicantName"],
                "course_name": row["course_name"],
                "file_name": row["file_name"],
                "pdf_path": row["pdf_path"],
                "isPassed": bool(row["isPassed"]),
                "aiFeedback": row["aiFeedback"],
                "aiFeedbackTable": json.loads(row["aiFeedbackTable"]) if row["aiFeedbackTable"] else [],
                "reviewStatus": row["reviewStatus"] or "submitted",
                "finalIsPassed": bool(row["finalIsPassed"]) if row["finalIsPassed"] is not None else None,
                "finalFeedback": row["finalFeedback"],
                "finalFeedbackTable": json.loads(row["finalFeedbackTable"]) if row["finalFeedbackTable"] else [],
                "reviewedAt": row["reviewedAt"],
                "applyDate": row["applyDate"],
                "applyTime": row["applyTime"],
                "labelIsCorrect": bool(row["labelIsCorrect"]),
                "correctedIsPassed": bool(row["correctedIsPassed"]) if row["correctedIsPassed"] is not None else None,
                "correctedFeedback": row["correctedFeedback"],
                "correctedFeedbackTable": json.loads(row["correctedFeedbackTable"]) if row["correctedFeedbackTable"] else [],
                "selectedRegions": json.loads(row["selectedRegions"]) if row["selectedRegions"] else [],
                "reviewer": row["reviewer"],
                "reviewComment": row["reviewComment"],
                "labeledAt": row["labeledAt"],
            }
        )

    return {
        "total": total,
        "records": records,
        "limit": limit,
        "offset": offset,
        "returned": len(records),
    }



# 4. 取回一筆「尚未被標記」的 history 記錄
def get_next_unlabeled_history():
    conn = _connect()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute(f'''
        SELECT h.applicantStdn,
               h.applicantNo,
               h.applicantName,
               h.file_name,
               h.pdf_path,
               h.isPassed,
               h.aiFeedback,
               h.aiFeedbackTable,
               h.reviewStatus,
               h.finalIsPassed,
               h.finalFeedback,
               h.finalFeedbackTable,
               h.reviewedAt,
               h.applyDate,
               h.applyTime
        FROM {TABLE_NAME} AS h
        LEFT JOIN {LABEL_TABLE_NAME} AS l
          ON h.applicantStdn = l.applicantStdn
         AND h.applicantNo  = l.applicantNo
        WHERE l.id IS NULL          -- 尚未有標記資料
        ORDER BY h.applyDate, h.applyTime
        LIMIT 1
    ''')

    row = c.fetchone()
    conn.close()

    if row is None:
        return None

    # 轉成 Python dict，方便給 Flask jsonify
    return {
        "applicantStdn": row["applicantStdn"],
        "applicantNo": row["applicantNo"],
        "applicantName": row["applicantName"],
        "file_name": row["file_name"],
        "pdf_path": row["pdf_path"],
        "isPassed": bool(row["isPassed"]),
        "aiFeedback": row["aiFeedback"],
        "aiFeedbackTable": json.loads(row["aiFeedbackTable"]) if row["aiFeedbackTable"] else [],
        "reviewStatus": row["reviewStatus"] or "submitted",
        "finalIsPassed": bool(row["finalIsPassed"]) if row["finalIsPassed"] is not None else None,
        "finalFeedback": row["finalFeedback"],
        "finalFeedbackTable": json.loads(row["finalFeedbackTable"]) if row["finalFeedbackTable"] else [],
        "reviewedAt": row["reviewedAt"],
        "applyDate": row["applyDate"],
        "applyTime": row["applyTime"],
    }


# 5. 寫入一筆人工標記結果
def insert_label_result(label_data: dict):
    """
    label_data 格式示例：
    {
        "applicantStdn": "A123456789",
        "applicantNo": 1,
        "labelIsCorrect": True,
        "correctedIsPassed": True or False or None,
        "correctedFeedback": "修正後意見 or None",
        "reviewer": "teacherA",
        "reviewComment": "哪裡錯、為什麼錯"
    }
    """
    conn = _connect()
    c = conn.cursor()

    c.execute(f'''
        INSERT INTO {LABEL_TABLE_NAME} (
            applicantStdn,
            applicantNo,
            labelIsCorrect,
            correctedIsPassed,
            correctedFeedback,
            correctedFeedbackTable,
            selectedRegions,
            reviewer,
            reviewComment
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        label_data["applicantStdn"],
        label_data["applicantNo"],
        1 if label_data.get("labelIsCorrect") else 0,
        label_data.get("correctedIsPassed"),
        label_data.get("correctedFeedback"),
        json.dumps(label_data.get("correctedFeedbackTable") or [], ensure_ascii=False),
        json.dumps(label_data.get("selectedRegions") or [], ensure_ascii=False),
        label_data.get("reviewer"),
        label_data.get("reviewComment"),
    ))

    conn.commit()
    conn.close()


# === Users Table（登入用）===
def init_users_table():
    conn = _connect()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'applicant',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def get_conn():
    return _connect()


def create_department(unit_no: int, unit_name: str, account: str, password_hash: str):
    conn = _connect()
    c = conn.cursor()
    c.execute(
        f"""
        INSERT INTO {DEPT_TABLE_NAME} (unit_no, unit_name, account, password_hash)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(unit_no) DO UPDATE SET
            unit_name = excluded.unit_name,
            account = excluded.account,
            password_hash = excluded.password_hash
        """,
        (unit_no, unit_name.strip(), account.strip().lower(), password_hash),
    )
    conn.commit()
    conn.close()


def get_department_by_account(account: str):
    conn = _connect()
    c = conn.cursor()
    c.execute(
        f"SELECT id, unit_no, unit_name, account, password_hash, created_at FROM {DEPT_TABLE_NAME} WHERE account=?",
        (account.strip().lower(),),
    )
    row = c.fetchone()
    conn.close()
    return row


def create_user(email, name, password_hash, role='applicant'):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO users(email,name,password_hash,role) VALUES(?,?,?,?)",
              (email.strip().lower(), name.strip(), password_hash, role))
    conn.commit()
    uid = c.lastrowid
    conn.close()
    return uid


def get_user_by_email(email):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id,email,name,password_hash,role,created_at FROM users WHERE email=?", (email.strip().lower(),))
    row = c.fetchone()
    conn.close()
    return row


def get_user_by_id(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id,email,name,password_hash,role,created_at FROM users WHERE id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row
