import importlib
import os
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


os.environ.setdefault("INVENTORY_TEST_MODE", "1")
os.environ.pop("SUPABASE_URL", None)
os.environ.pop("SUPABASE_KEY", None)


@pytest.fixture
def app_module():
    module = importlib.import_module("app")
    return module


@pytest.fixture
def client(app_module):
    from fastapi.testclient import TestClient

    with TestClient(app_module.app) as test_client:
        yield test_client

