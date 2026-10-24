import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
from backend.app import create_app
from backend.service import MealService

@pytest.fixture
def service():return MealService()

@pytest.fixture
def client(service):return create_app(service).test_client()
