from .analyze import analyze_bp
from .auth import auth_bp
from .core import core_bp
from .departments import departments_bp
from .label import label_bp
from .teacher import teacher_bp

__all__ = [
    "analyze_bp",
    "auth_bp",
    "core_bp",
    "departments_bp",
    "label_bp",
    "teacher_bp",
]
