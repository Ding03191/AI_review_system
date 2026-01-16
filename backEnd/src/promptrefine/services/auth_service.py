from werkzeug.security import check_password_hash, generate_password_hash

from ..db import create_user as db_create_user
from ..db import get_user_by_email as db_get_user_by_email


def create_user(email, name, password):
    password_hash = generate_password_hash(password)
    return db_create_user(email, name, password_hash)


def get_user_by_email(email):
    return db_get_user_by_email(email)


def verify_password(row, password):
    if not row:
        return False
    stored_hash = row[3]
    return check_password_hash(stored_hash, password)
