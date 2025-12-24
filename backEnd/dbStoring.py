import sqlite3
import os
import shutil
# from datetime import datetime


_BASE_DIR = os.path.dirname(__file__)
_LEGACY_DB_PATH = os.path.join(_BASE_DIR, "scoringHistory.sqlite")
_DEFAULT_DB_PATH = os.path.join(_BASE_DIR, "db", "scoringHistory.sqlite")
DB_NAME = os.environ.get("DB_PATH", _DEFAULT_DB_PATH)
TABLE_NAME = 'history'
LABEL_TABLE_NAME = "history_labels"


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
            file_name TEXT,
            pdf_path TEXT,
            isPassed BOOLEAN,
            aiFeedback TEXT,
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

            labelIsCorrect INTEGER NOT NULL,     -- 1 = AI 整體正確, 0 = 有錯
            correctedIsPassed BOOLEAN,           -- 若有修正後的 isPassed
            correctedFeedback TEXT,              -- 若有修正後的 aiFeedback

            reviewer TEXT,                       -- 標記人，例如 teacherA
            reviewComment TEXT,                  -- 備註
            labeledAt TEXT DEFAULT (datetime('now','localtime')),

            FOREIGN KEY (applicantStdn, applicantNo)
                REFERENCES {TABLE_NAME}(applicantStdn, applicantNo)
        )
    ''')
    conn.commit()

    # Backward-compatible schema migration: add columns if old DB already exists.
    existing_cols = {row[1] for row in c.execute(f"PRAGMA table_info({TABLE_NAME})").fetchall()}
    for col, col_type in (("file_name", "TEXT"), ("pdf_path", "TEXT")):
        if col not in existing_cols:
            c.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN {col} {col_type}")

    conn.commit()
    conn.close()

# 2. Insert a record


def insert_scoring_result(data):
    conn = _connect()
    c = conn.cursor()

    c.execute(f'''
        INSERT OR REPLACE INTO {TABLE_NAME} (
            applicantStdn,
            applicantNo,
            applicantName,
            file_name,
            pdf_path,
            isPassed,
            aiFeedback,
            applyDate,
            applyTime
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data['applicantStdn'],
        data['applicantNo'],
        data['applicantName'],
        data.get('file_name'),
        data.get('pdf_path'),
        int(data['isPassed']),  # Store boolean as 0 or 1
        data['aiFeedback'],
        data['applyDate'],
        data['applyTime']
    ))

    conn.commit()
    conn.close()

# 3. Optional: Fetch all history


def fetch_all_results():
    conn = _connect()
    c = conn.cursor()
    c.execute(f'SELECT * FROM {TABLE_NAME}')
    results = c.fetchall()
    conn.close()
    return results

# init_db()  # 已經call過了
# insert_scoring_result(your_json_dict)


# 4. 取得一筆「尚未被標記」的 history 記錄
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
               h.applyDate,
               h.applyTime
        FROM {TABLE_NAME} AS h
        LEFT JOIN {LABEL_TABLE_NAME} AS l
          ON h.applicantStdn = l.applicantStdn
         AND h.applicantNo  = l.applicantNo
        WHERE l.id IS NULL          -- 還沒有標記過的
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
        "applyDate": row["applyDate"],
        "applyTime": row["applyTime"],
    }


# 5. 寫入一筆人工標記結果
def insert_label_result(label_data: dict):
    """
    label_data 格式示意：
    {
        "applicantStdn": "A123456789",
        "applicantNo": 1,
        "labelIsCorrect": True,
        "correctedIsPassed": True 或 False 或 None,
        "correctedFeedback": "修正後意見或 None",
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
            reviewer,
            reviewComment
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        label_data["applicantStdn"],
        label_data["applicantNo"],
        1 if label_data.get("labelIsCorrect") else 0,
        label_data.get("correctedIsPassed"),
        label_data.get("correctedFeedback"),
        label_data.get("reviewer"),
        label_data.get("reviewComment"),
    ))

    conn.commit()
    conn.close()


# === Users Table（登入用） ===
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

