from werkzeug.security import check_password_hash, generate_password_hash

from ..db import dbStoring as db


def create_user(email, name, password, role="applicant"):
    password_hash = generate_password_hash(password)
    return db.create_user(email, name, password_hash, role)


def get_user_by_email(email):
    return db.get_user_by_email(email)


def verify_password(row, password):
    return row and check_password_hash(row[3], password)
