import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from hap_ctf.api import app


@pytest.fixture
def test_client():
    with TestClient(app) as client:
        yield client


def create_submission_zip(code: str) -> io.BytesIO:
    """Create a submission zip file with the given code in __init__.py."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zip_file:
        zip_file.writestr("__init__.py", code)
    zip_buffer.seek(0)
    return zip_buffer


def test_run_code_valid_submission(test_client):
    code = """
def main():
    return "Hello from test!"
"""
    zip_data = create_submission_zip(code)

    response = test_client.post(
        "/run_code/", files={"file": ("test.zip", zip_data, "application/zip")}
    )

    assert response.status_code == 200
    assert response.json() == {"result": "Hello from test!"}


@pytest.mark.slow
def test_run_code_timeout(test_client):
    code = """
import time

def main():
    time.sleep(120)  # Sleep for 2 minutes, well over the 60 second timeout
    return "Should not reach here"
"""
    zip_data = create_submission_zip(code)

    response = test_client.post(
        "/run_code/", files={"file": ("test.zip", zip_data, "application/zip")}
    )

    assert response.status_code == 408
    assert "Code execution timed out" in response.json()["detail"]


def test_run_code_syntax_error(test_client):
    code = """
def main():
    this is not valid python
    return "Should not reach here"
"""
    zip_data = create_submission_zip(code)

    response = test_client.post(
        "/run_code/", files={"file": ("test.zip", zip_data, "application/zip")}
    )

    assert response.status_code == 500
    error_detail = response.json()["detail"]
    assert error_detail.startswith("SyntaxError:")
    assert "invalid syntax" in error_detail.lower()


def test_run_code_runtime_error(test_client):
    code = """
def main():
    return 1/0  # Division by zero error
"""
    zip_data = create_submission_zip(code)

    response = test_client.post(
        "/run_code/", files={"file": ("test.zip", zip_data, "application/zip")}
    )

    assert response.status_code == 500
    assert "ZeroDivisionError" in response.json()["detail"]


def test_run_code_invalid_file_type(test_client):
    response = test_client.post(
        "/run_code/", files={"file": ("test.txt", b"not a zip file", "text/plain")}
    )

    assert response.status_code == 400
    assert "Only .zip files are allowed" in response.json()["detail"]


def test_run_code_missing_main(test_client):
    code = """
def not_main():
    return "This won't be called"
"""
    zip_data = create_submission_zip(code)

    response = test_client.post(
        "/run_code/", files={"file": ("test.zip", zip_data, "application/zip")}
    )

    assert response.status_code == 500
    assert "No main() function found" in response.json()["detail"]


def test_run_code_sandbox_restrictions(test_client):
    code = """
import os

def main():
    try:
        os.system('echo "Should be blocked"')
        return "Security failure - command executed"
    except Exception as e:
        return str(e)
"""
    zip_data = create_submission_zip(code)

    response = test_client.post(
        "/run_code/", files={"file": ("test.zip", zip_data, "application/zip")}
    )

    assert response.status_code == 200
    # The exact error message might vary, but it should indicate the operation was blocked
    assert "system" in response.json()["result"].lower()
