import os
import glob
import pytest
from fastapi.testclient import TestClient
from hap_ctf.api import app
from hap_ctf.config import Settings, get_settings

@pytest.fixture
def test_client():
    app.dependency_overrides[get_settings] = lambda: Settings(process_timeout=1)
    with TestClient(app) as client:
        yield client
    app.dependency_overrides = {}

@pytest.mark.parametrize(
    "archive_path",
    glob.glob(os.path.join(".", "zip-tests", "*.zip")) + 
    glob.glob(os.path.join(".", "zip-tests", "*.gz"))
)
def test_run_archives(test_client, archive_path):
    with open(archive_path, "rb") as f:
        data = f.read()
    if archive_path.endswith(".zip"):
        mime = "application/zip"
        resp = test_client.post("/run_code/", files={"file": (os.path.basename(archive_path), data, mime)})
        assert resp.status_code in [200, 408, 500], f"Unexpected status {resp.status_code} for {archive_path}"
    else:
        mime = "application/gzip"
        resp = test_client.post("/run_code/", files={"file": (os.path.basename(archive_path), data, mime)})
        assert resp.status_code == 400
        assert "Only .zip files are allowed" in resp.json()["detail"]
