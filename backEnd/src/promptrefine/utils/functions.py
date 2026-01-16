import os

_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_TOKEN_FILE = os.path.join(_BACKEND_DIR, 'tokenUsed.txt')


def read_file_to_string(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()


def tokenUsed(new_tokens):
    file_path = _TOKEN_FILE
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            token_count = int(file.read().strip())
    else:
        token_count = 0
    token_count += new_tokens
    with open(file_path, 'w') as file:
        file.write(str(token_count))
