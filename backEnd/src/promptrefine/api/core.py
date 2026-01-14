from flask import Blueprint


core_bp = Blueprint("core", __name__)


@core_bp.route("/", methods=["GET"])
def hello():
    return "Hello World"
