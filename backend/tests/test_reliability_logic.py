import contextlib
from concurrent.futures import TimeoutError
from unittest.mock import MagicMock, patch

import pytest

from backend.ingestion.worker import _mark_task_error, run_worker_loop


def test_mark_task_error():
    mock_supabase = MagicMock()
    task_id = "test-task-123"
    message = "Test error message"

    _mark_task_error(mock_supabase, task_id, message)

    mock_supabase.table.assert_called_with("ingestion_tasks")
    mock_supabase.table().update.assert_called()
    # Check that update includes status: error and the message
    args, _ = mock_supabase.table().update.call_args
    assert args[0]["status"] == "error"
    assert args[0]["message"] == message


@patch("backend.ingestion.worker.get_supabase")
@patch("backend.ingestion.worker.nlp_executor")
@patch("backend.ingestion.worker.process_chunks_batch")
@patch("time.sleep", side_effect=InterruptedError)  # To break the while True loop
def test_worker_timeout_handling(mock_process, mock_executor, mock_get_supabase, mock_sleep):
    mock_supabase = MagicMock()
    mock_get_supabase.return_value = mock_supabase

    # Mock some pending chunks
    mock_supabase.table().select().eq().order().limit().execute.return_value.data = [
        {"id": "chunk1", "task_id": "task1", "content": "hello"}
    ]

    # Mock future.result() to raise TimeoutError
    mock_future = MagicMock()
    mock_future.result.side_effect = TimeoutError()
    mock_executor.submit.return_value = mock_future

    with contextlib.suppress(InterruptedError):
        run_worker_loop()

    # Verify that nlp_executor.shutdown was called to kill the stuck process
    mock_executor.shutdown.assert_called()

    # Verify that the task was marked as error due to timeout
    mock_supabase.table().update.assert_any_call(
        pytest.match({"status": "error", "message": pytest.match("Timed out")})
    )
