from werkzeug.security import check_password_hash, generate_password_hash

from ..db import create_user as db_create_user
from ..db import get_user_by_email as db_get_user_by_email
from ..db import get_user_by_id as db_get_user_by_id


def create_user(email, name, password, role='applicant'):
    password_hash = generate_password_hash(password)
    return db_create_user(email, name, password_hash, role=role)


def get_user_by_email(email):
    return db_get_user_by_email(email)


def get_user_by_id(user_id):
    return db_get_user_by_id(user_id)


def verify_password(row, password):
    if not row:
        return False
    stored_hash = row[3]
    return check_password_hash(stored_hash, password)
