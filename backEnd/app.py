import os
import sys
from promptrefine import create_app


BACKEND_DIR = os.path.abspath(os.path.dirname(__file__))
SRC_DIR = os.path.join(BACKEND_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
