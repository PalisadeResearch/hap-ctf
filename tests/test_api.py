import io
import threading
import time
import zipfile

import pytest
from fastapi.testclient import TestClient
from memory_profiler import memory_usage

from hap_ctf.api import app, get_settings
from hap_ctf.config import Settings


@pytest.fixture
def test_client():
    app.dependency_overrides[get_settings] = lambda: Settings(process_timeout=1)

    with TestClient(app) as client:
        yield client

    app.dependency_overrides = {}


@pytest.fixture(autouse=True)
def profile_memory(request, capsys):
    """
    Fixture that continuously measures memory usage during a test by sampling
    every 0.1 seconds, then reports the maximum delta observed from the baseline.
    """
    mem_samples = []
    stop_event = threading.Event()

    def sample_memory():
        # Continuously sample memory usage until stop_event is set.
        while not stop_event.is_set():
            current_usage = sum(
                memory_usage(
                    -1, multiprocess=True, include_children=True, interval=0.0
                )[0]
            )
            mem_samples.append(current_usage)
            time.sleep(0.1)  # Sample every 0.1 seconds.

    # Record the baseline memory usage before starting the sampling thread.
    baseline = sum(
        memory_usage(-1, multiprocess=True, include_children=True, interval=0.0)[0]
    )
    thread = threading.Thread(target=sample_memory)
    thread.start()

    yield  # Run the actual test.

    # Signal the sampling thread to stop and wait for it to finish.
    stop_event.set()
    thread.join()

    # Determine the maximum memory usage observed during the test.
    max_usage = max(mem_samples, default=baseline)
    mem_delta = max_usage - baseline
    with capsys.disabled():
        print(f"\nPeak RAM usage: {mem_delta:.4f} MiB")


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

    assert response.status_code == 408
