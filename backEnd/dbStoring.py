import sqlite3
import os
# from datetime import datetime


DB_NAME = os.path.join(os.path.dirname(__file__), 'scoringHistory.sqlite')
# DB_NAME = 'backEnd/scoringHistory.sqlite'
TABLE_NAME = 'history'


# 1. Create the table if it doesn't exist
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(f'''
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            applicantStdn TEXT,
            applicantNo INTEGER,
            applicantName TEXT,
            isPassed BOOLEAN,
            aiFeedback TEXT,
            applyDate TEXT,
            applyTime TEXT,
            PRIMARY KEY (applicantStdn, applicantNo)
        )
    ''')
    conn.commit()
    conn.close()

# 2. Insert a record


def insert_scoring_result(data):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute(f'''
        INSERT OR REPLACE INTO {TABLE_NAME} (
            applicantStdn,
            applicantNo,
            applicantName,
            isPassed,
            aiFeedback,
            applyDate,
            applyTime
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        data['applicantStdn'],
        data['applicantNo'],
        data['applicantName'],
        int(data['isPassed']),  # Store boolean as 0 or 1
        data['aiFeedback'],
        data['applyDate'],
        data['applyTime']
    ))

    conn.commit()
    conn.close()

# 3. Optional: Fetch all history


def fetch_all_results():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(f'SELECT * FROM {TABLE_NAME}')
    results = c.fetchall()
    conn.close()
    return results

# init_db()  # 已經call過了
# insert_scoring_result(your_json_dict)