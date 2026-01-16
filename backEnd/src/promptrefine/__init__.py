import logging


def create_app():
    from flask import Flask
    from flask_cors import CORS

    from .config import Config
    from .db import dbStoring as db
    from .api.core import core_bp
    from .api.auth import auth_bp
    from .api.analyze import analyze_bp

    app = Flask(__name__)
    app.config.from_object(Config)

    CORS(app, supports_credentials=True)

    if not app.config["SECRET_KEY"]:
        raise ValueError("Error: SECRET_KEY environment variable is not set!")

    db.init_db()
    db.init_users_table()

    app.register_blueprint(core_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(analyze_bp)

    logging.getLogger(__name__).info("DB in use: %s", db.DB_NAME)
    return app
