import os


_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_TOKEN_FILE = os.path.join(_BACKEND_DIR, "tokenUsed.txt")


def read_file_to_string(file_path):
    print(f"Trying to open file at: {os.path.abspath(file_path)}")  # Print the absolute path
    with open(file_path, "r", encoding="utf-8") as file:
        file_content = file.read()
    return file_content


def tokenUsed(new_tokens):
    file_path = _TOKEN_FILE

    # Read the current token count from the file
    if os.path.exists(file_path):
        with open(file_path, "r") as file:
            token_count = int(file.read().strip())
    else:
        token_count = 0

    # Add the new tokens to the current count
    token_count += new_tokens

    # Write the updated token count back to the file
    with open(file_path, "w") as file:
        file.write(str(token_count))
