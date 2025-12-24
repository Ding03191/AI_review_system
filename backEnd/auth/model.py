from werkzeug.security import generate_password_hash, check_password_hash


def create_user(conn, email, name, password, role='applicant'):
    h = generate_password_hash(password)
    cur = conn.cursor()
    cur.execute("INSERT INTO users(email,name,password_hash,role) VALUES(?,?,?,?)",
                (email.strip().lower(), name.strip(), h, role))
    conn.commit()
    return cur.lastrowid


def get_user_by_email(conn, email):
    cur = conn.cursor()
    cur.execute("SELECT id,email,name,password_hash,role,created_at FROM users WHERE email=?", (email.strip().lower(),))
    row = cur.fetchone()
    return row


def verify_password(row, password):
    return row and check_password_hash(row[3], password)  # 第4欄是 password_hash
