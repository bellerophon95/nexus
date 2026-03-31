import pytest
from unittest.mock import patch, MagicMock
import os

# Set testing environment variables before any other imports
os.environ["ENV"] = "testing"
os.environ["DEBUG"] = "false"
os.environ["SUPABASE_URL"] = "http://localhost:8000"
os.environ["SUPABASE_ANON_KEY"] = "mock_key"
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "mock_service_key"
os.environ["OPENAI_API_KEY"] = "sk-mock"
os.environ["ANTHROPIC_API_KEY"] = "sk-ant"

@pytest.fixture(autouse=True)
def mock_supabase():
    """Mock out Supabase to avoid hitting real DB during CI runs."""
    with patch("backend.database.supabase.get_supabase") as mock_sync:
        with patch("backend.database.supabase.get_async_supabase") as mock_async:
            # Setup a basic mock response object
            mock_client = MagicMock()
            mock_sync.return_value = mock_client
            
            # Setup async mock
            mock_async_client = MagicMock()
            mock_async.return_value = mock_async_client
            
            yield mock_sync, mock_async

@pytest.fixture(autouse=True)
def mock_tracing():
    """Mock out tracing to avoid initializing Langfuse in CI."""
    with patch("backend.observability.tracing.init_tracing") as mock_init:
        mock_init.return_value = True
        yield mock_init

@pytest.fixture(autouse=True)
def mock_guard_warmup():
    """Mock out guardrail warmup to avoid loading heavy models in CI."""
    with patch("backend.guardrails.input_guard.warmup_guardrails") as mock_warmup:
        # Use a real completed future for the async task if needed, 
        # but usually mocking the task creation in main.py is enough.
        yield mock_warmup
