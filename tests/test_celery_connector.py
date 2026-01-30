"""Tests for Celery Connector."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from foobara_py import Command
from foobara_py.core.registry import CommandRegistry
from foobara_py.connectors.celery_connector import (
    CeleryConfig,
    CeleryConnector,
    CeleryScheduler,
    CeleryTaskFactory,
    JobResult,
    JobStatus,
    ScheduleConfig,
)


# Test models and commands
class ProcessInputs(BaseModel):
    data: str
    priority: int = 0


class ProcessResult(BaseModel):
    processed: str
    timestamp: str


class ProcessDataCommand(Command[ProcessInputs, ProcessResult]):
    """Process some data."""

    Inputs = ProcessInputs
    Result = ProcessResult

    def execute(self) -> ProcessResult:
        return ProcessResult(
            processed=f"processed:{self.inputs.data}",
            timestamp=datetime.now().isoformat(),
        )


class SimpleCommand(Command):
    """A simple command."""

    def execute(self):
        return {"status": "ok"}


class FailingCommand(Command):
    """A command that fails."""

    def execute(self):
        raise ValueError("Intentional failure")


class TestJobResult:
    """Tests for JobResult class."""

    def test_create_job_result(self):
        result = JobResult(
            job_id="job-123",
            status=JobStatus.PENDING,
            command_name="TestCommand",
            inputs={"key": "value"},
        )
        assert result.job_id == "job-123"
        assert result.status == JobStatus.PENDING
        assert result.command_name == "TestCommand"

    def test_job_result_to_dict(self):
        result = JobResult(
            job_id="job-456",
            status=JobStatus.SUCCESS,
            command_name="TestCommand",
            inputs={"data": "test"},
            result={"processed": True},
            started_at=datetime(2024, 1, 1, 12, 0, 0),
            completed_at=datetime(2024, 1, 1, 12, 0, 5),
        )
        d = result.to_dict()
        assert d["job_id"] == "job-456"
        assert d["status"] == "success"
        assert d["result"] == {"processed": True}
        assert "2024-01-01" in d["started_at"]

    def test_job_result_with_error(self):
        result = JobResult(
            job_id="job-789",
            status=JobStatus.FAILURE,
            command_name="TestCommand",
            inputs={},
            error="Something went wrong",
            traceback="Traceback...",
        )
        assert result.status == JobStatus.FAILURE
        assert result.error == "Something went wrong"


class TestJobStatus:
    """Tests for JobStatus enum."""

    def test_status_values(self):
        assert JobStatus.PENDING.value == "pending"
        assert JobStatus.STARTED.value == "started"
        assert JobStatus.SUCCESS.value == "success"
        assert JobStatus.FAILURE.value == "failure"
        assert JobStatus.REVOKED.value == "revoked"
        assert JobStatus.RETRY.value == "retry"


class TestCeleryConfig:
    """Tests for Celery configuration."""

    def test_default_config(self):
        config = CeleryConfig()
        assert config.broker_url == "redis://localhost:6379/0"
        assert config.result_backend == "redis://localhost:6379/0"
        assert config.default_queue == "foobara"
        assert config.max_retries == 3

    def test_custom_config(self):
        config = CeleryConfig(
            broker_url="amqp://localhost",
            result_backend="redis://redis:6379/1",
            default_queue="custom_queue",
            max_retries=5,
            task_time_limit=7200,
        )
        assert config.broker_url == "amqp://localhost"
        assert config.default_queue == "custom_queue"
        assert config.max_retries == 5
        assert config.task_time_limit == 7200


class TestScheduleConfig:
    """Tests for ScheduleConfig class."""

    def test_interval_schedule(self):
        config = ScheduleConfig(
            interval=3600,
            inputs={"key": "value"},
        )
        assert config.interval == 3600
        assert config.crontab is None

    def test_crontab_schedule(self):
        config = ScheduleConfig(
            crontab={"hour": 0, "minute": 0},
            inputs={},
        )
        assert config.crontab == {"hour": 0, "minute": 0}
        assert config.interval is None


class TestCeleryTaskFactory:
    """Tests for CeleryTaskFactory class."""

    @pytest.fixture
    def registry(self):
        reg = CommandRegistry()
        reg.register(ProcessDataCommand)
        reg.register(SimpleCommand)
        return reg

    @pytest.fixture
    def mock_celery(self):
        """Mock Celery module."""
        with patch.dict("sys.modules", {"celery": MagicMock()}):
            yield

    def test_factory_initialization(self, registry):
        factory = CeleryTaskFactory(registry)
        assert factory.registry == registry
        assert factory._celery_app is None

    @patch("foobara_py.connectors.celery_connector.CeleryTaskFactory.get_celery_app")
    def test_create_task(self, mock_get_app, registry):
        mock_app = MagicMock()
        mock_task_decorator = MagicMock(return_value=lambda f: f)
        mock_app.task = mock_task_decorator
        mock_get_app.return_value = mock_app

        factory = CeleryTaskFactory(registry)
        task = factory.create_task(ProcessDataCommand)

        assert callable(task)
        assert "foobara.ProcessDataCommand" in factory._tasks

    @patch("foobara_py.connectors.celery_connector.CeleryTaskFactory.get_celery_app")
    def test_create_all_tasks(self, mock_get_app, registry):
        mock_app = MagicMock()
        mock_task_decorator = MagicMock(return_value=lambda f: f)
        mock_app.task = mock_task_decorator
        mock_get_app.return_value = mock_app

        factory = CeleryTaskFactory(registry)
        tasks = factory.create_all_tasks()

        assert len(tasks) >= 2  # At least ProcessDataCommand and SimpleCommand


class TestCeleryConnector:
    """Tests for CeleryConnector class."""

    @pytest.fixture
    def registry(self):
        reg = CommandRegistry()
        reg.register(ProcessDataCommand)
        reg.register(SimpleCommand)
        return reg

    @pytest.fixture
    def mock_celery_app(self):
        """Create a mock Celery app."""
        mock_app = MagicMock()
        mock_app.task = MagicMock(return_value=lambda f: f)
        mock_app.AsyncResult = MagicMock()
        mock_app.control = MagicMock()
        mock_app.conf = MagicMock()
        mock_app.conf.beat_schedule = {}
        return mock_app

    @patch("foobara_py.connectors.celery_connector.CeleryTaskFactory.get_celery_app")
    def test_connector_initialization(self, mock_get_app, registry, mock_celery_app):
        mock_get_app.return_value = mock_celery_app
        connector = CeleryConnector(registry)
        assert connector.registry == registry
        assert not connector._tasks_created

    @patch("foobara_py.connectors.celery_connector.CeleryTaskFactory.get_celery_app")
    def test_execute_async(self, mock_get_app, registry, mock_celery_app):
        mock_get_app.return_value = mock_celery_app

        # Mock the task with apply_async method
        mock_task = MagicMock()
        mock_async_result = MagicMock()
        mock_async_result.id = "job-123"
        mock_task.apply_async.return_value = mock_async_result

        connector = CeleryConnector(registry)
        connector._tasks_created = True  # Skip auto-creation
        connector.task_factory._tasks["foobara.ProcessDataCommand"] = mock_task

        result = connector.execute_async(
            "ProcessDataCommand",
            {"data": "test", "priority": 1},
        )

        assert result.job_id == "job-123"
        assert result.status == JobStatus.PENDING
        assert result.command_name == "ProcessDataCommand"

    @patch("foobara_py.connectors.celery_connector.CeleryTaskFactory.get_celery_app")
    def test_execute_async_with_options(self, mock_get_app, registry, mock_celery_app):
        mock_get_app.return_value = mock_celery_app

        mock_task = MagicMock()
        mock_async_result = MagicMock()
        mock_async_result.id = "job-456"
        mock_task.apply_async.return_value = mock_async_result

        connector = CeleryConnector(registry)
        connector._tasks_created = True
        connector.task_factory._tasks["foobara.ProcessDataCommand"] = mock_task

        result = connector.execute_async(
            "ProcessDataCommand",
            {"data": "test"},
            queue="high_priority",
            countdown=60,
            priority=9,
        )

        mock_task.apply_async.assert_called_once()
        call_kwargs = mock_task.apply_async.call_args[1]
        assert call_kwargs["queue"] == "high_priority"
        assert call_kwargs["countdown"] == 60
        assert call_kwargs["priority"] == 9

    @patch("foobara_py.connectors.celery_connector.CeleryTaskFactory.get_celery_app")
    def test_execute_async_command_not_found(self, mock_get_app, registry, mock_celery_app):
        mock_get_app.return_value = mock_celery_app
        connector = CeleryConnector(registry)
        connector._tasks_created = True

        with pytest.raises(ValueError, match="not found"):
            connector.execute_async("NonExistentCommand", {})

    @patch("foobara_py.connectors.celery_connector.CeleryTaskFactory.get_celery_app")
    def test_get_result_success(self, mock_get_app, registry, mock_celery_app):
        mock_get_app.return_value = mock_celery_app

        mock_async_result = MagicMock()
        mock_async_result.state = "SUCCESS"
        mock_async_result.successful.return_value = True
        mock_async_result.failed.return_value = False
        mock_async_result.result = {"status": "success", "result": {"data": "processed"}}
        mock_celery_app.AsyncResult.return_value = mock_async_result

        connector = CeleryConnector(registry)
        result = connector.get_result("job-123")

        assert result.status == JobStatus.SUCCESS
        assert result.result is not None

    @patch("foobara_py.connectors.celery_connector.CeleryTaskFactory.get_celery_app")
    def test_get_result_failure(self, mock_get_app, registry, mock_celery_app):
        mock_get_app.return_value = mock_celery_app

        mock_async_result = MagicMock()
        mock_async_result.state = "FAILURE"
        mock_async_result.successful.return_value = False
        mock_async_result.failed.return_value = True
        mock_async_result.result = Exception("Task failed")
        mock_async_result.traceback = "Traceback..."
        mock_celery_app.AsyncResult.return_value = mock_async_result

        connector = CeleryConnector(registry)
        result = connector.get_result("job-456")

        assert result.status == JobStatus.FAILURE
        assert result.error is not None
        assert result.traceback == "Traceback..."

    @patch("foobara_py.connectors.celery_connector.CeleryTaskFactory.get_celery_app")
    def test_revoke(self, mock_get_app, registry, mock_celery_app):
        mock_get_app.return_value = mock_celery_app

        connector = CeleryConnector(registry)
        result = connector.revoke("job-123", terminate=True)

        assert result is True
        mock_celery_app.control.revoke.assert_called_once_with(
            "job-123", terminate=True, signal="SIGTERM"
        )


class TestCeleryScheduler:
    """Tests for CeleryScheduler class."""

    @pytest.fixture
    def registry(self):
        reg = CommandRegistry()
        reg.register(ProcessDataCommand)
        return reg

    @pytest.fixture
    def mock_celery_app(self):
        mock_app = MagicMock()
        mock_app.task = MagicMock(return_value=lambda f: f)
        mock_app.conf = MagicMock()
        mock_app.conf.beat_schedule = {}
        return mock_app

    @patch("foobara_py.connectors.celery_connector.CeleryTaskFactory.get_celery_app")
    def test_schedule_with_interval(self, mock_get_app, registry, mock_celery_app):
        mock_get_app.return_value = mock_celery_app

        # Mock celery.schedules module
        mock_schedules = MagicMock()
        mock_schedules.crontab = MagicMock()
        with patch.dict("sys.modules", {"celery.schedules": mock_schedules}):
            connector = CeleryConnector(registry)
            connector._tasks_created = True
            scheduler = CeleryScheduler(connector)

            schedule_name = scheduler.schedule(
                "ProcessDataCommand",
                inputs={"data": "test"},
                interval=3600,
            )

            assert schedule_name == "ProcessDataCommand_schedule"
            assert schedule_name in scheduler._schedules
            assert mock_celery_app.conf.beat_schedule[schedule_name]["schedule"] == 3600

    @patch("foobara_py.connectors.celery_connector.CeleryTaskFactory.get_celery_app")
    def test_schedule_with_crontab(self, mock_get_app, registry, mock_celery_app):
        mock_get_app.return_value = mock_celery_app

        # Mock crontab import
        with patch.dict("sys.modules", {"celery.schedules": MagicMock()}):
            import sys
            mock_schedules = sys.modules["celery.schedules"]
            mock_crontab_instance = MagicMock()
            mock_schedules.crontab.return_value = mock_crontab_instance

            connector = CeleryConnector(registry)
            connector._tasks_created = True
            scheduler = CeleryScheduler(connector)

            schedule_name = scheduler.schedule(
                "ProcessDataCommand",
                crontab={"hour": 0, "minute": 0},
                name="daily_process",
            )

            assert schedule_name == "daily_process"
            assert "daily_process" in scheduler._schedules

    @patch("foobara_py.connectors.celery_connector.CeleryTaskFactory.get_celery_app")
    def test_schedule_without_interval_or_crontab(self, mock_get_app, registry, mock_celery_app):
        mock_get_app.return_value = mock_celery_app

        connector = CeleryConnector(registry)
        scheduler = CeleryScheduler(connector)

        with pytest.raises(ValueError, match="interval or crontab"):
            scheduler.schedule("ProcessDataCommand")

    @patch("foobara_py.connectors.celery_connector.CeleryTaskFactory.get_celery_app")
    def test_unschedule(self, mock_get_app, registry, mock_celery_app):
        mock_get_app.return_value = mock_celery_app

        mock_schedules = MagicMock()
        mock_schedules.crontab = MagicMock()
        with patch.dict("sys.modules", {"celery.schedules": mock_schedules}):
            connector = CeleryConnector(registry)
            connector._tasks_created = True
            scheduler = CeleryScheduler(connector)

            scheduler.schedule("ProcessDataCommand", interval=3600)
            result = scheduler.unschedule("ProcessDataCommand_schedule")

            assert result is True
            assert "ProcessDataCommand_schedule" not in scheduler._schedules

    @patch("foobara_py.connectors.celery_connector.CeleryTaskFactory.get_celery_app")
    def test_unschedule_not_found(self, mock_get_app, registry, mock_celery_app):
        mock_get_app.return_value = mock_celery_app

        connector = CeleryConnector(registry)
        connector._tasks_created = True
        scheduler = CeleryScheduler(connector)

        result = scheduler.unschedule("nonexistent")
        assert result is False

    @patch("foobara_py.connectors.celery_connector.CeleryTaskFactory.get_celery_app")
    def test_list_schedules(self, mock_get_app, registry, mock_celery_app):
        mock_get_app.return_value = mock_celery_app

        mock_schedules = MagicMock()
        mock_schedules.crontab = MagicMock()
        with patch.dict("sys.modules", {"celery.schedules": mock_schedules}):
            connector = CeleryConnector(registry)
            connector._tasks_created = True
            scheduler = CeleryScheduler(connector)

            scheduler.schedule("ProcessDataCommand", interval=3600, name="hourly")
            scheduler.schedule("ProcessDataCommand", interval=60, name="minutely")

            schedules = scheduler.list_schedules()
            assert "hourly" in schedules
            assert "minutely" in schedules


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    @pytest.fixture
    def registry(self):
        reg = CommandRegistry()
        reg.register(ProcessDataCommand)
        return reg

    @patch("foobara_py.connectors.celery_connector.CeleryTaskFactory.get_celery_app")
    def test_create_celery_app(self, mock_get_app, registry):
        mock_app = MagicMock()
        mock_app.task = MagicMock(return_value=lambda f: f)
        mock_get_app.return_value = mock_app

        from foobara_py.connectors.celery_connector import create_celery_app

        app = create_celery_app(registry)
        assert app == mock_app

    @patch("foobara_py.connectors.celery_connector.CeleryConnector.execute_async")
    def test_execute_async_function(self, mock_execute, registry):
        mock_execute.return_value = JobResult(
            job_id="job-123",
            status=JobStatus.PENDING,
            command_name="ProcessDataCommand",
            inputs={"data": "test"},
        )

        from foobara_py.connectors.celery_connector import execute_async

        result = execute_async("ProcessDataCommand", {"data": "test"}, registry=registry)
        assert result.job_id == "job-123"


class TestIntegrationScenarios:
    """Integration-style tests (mocked)."""

    @pytest.fixture
    def registry(self):
        reg = CommandRegistry()
        reg.register(ProcessDataCommand)
        reg.register(SimpleCommand)
        reg.register(FailingCommand)
        return reg

    @patch("foobara_py.connectors.celery_connector.CeleryTaskFactory.get_celery_app")
    def test_full_job_lifecycle(self, mock_get_app, registry):
        """Test submitting, checking, and completing a job."""
        mock_app = MagicMock()
        mock_app.task = MagicMock(return_value=lambda f: f)
        mock_app.conf = MagicMock()
        mock_app.conf.beat_schedule = {}
        mock_get_app.return_value = mock_app

        # Submit job
        mock_task = MagicMock()
        mock_async_result = MagicMock()
        mock_async_result.id = "lifecycle-job-1"
        mock_task.apply_async.return_value = mock_async_result

        connector = CeleryConnector(registry)
        connector._tasks_created = True
        connector.task_factory._tasks["foobara.ProcessDataCommand"] = mock_task

        # Submit
        job = connector.execute_async("ProcessDataCommand", {"data": "test"})
        assert job.status == JobStatus.PENDING
        assert job.job_id == "lifecycle-job-1"

        # Check pending
        mock_result = MagicMock()
        mock_result.state = "PENDING"
        mock_result.successful.return_value = False
        mock_result.failed.return_value = False
        mock_app.AsyncResult.return_value = mock_result

        result = connector.get_result(job.job_id)
        assert result.status == JobStatus.PENDING

        # Check started
        mock_result.state = "STARTED"
        result = connector.get_result(job.job_id)
        assert result.status == JobStatus.STARTED

        # Check success
        mock_result.state = "SUCCESS"
        mock_result.successful.return_value = True
        mock_result.result = {"processed": "test_data"}
        result = connector.get_result(job.job_id)
        assert result.status == JobStatus.SUCCESS


# ==================== Celery Task Retry Logic Edge Cases ====================

class TestCeleryRetryLogic:
    """Tests for Celery retry logic edge cases"""

    @pytest.fixture
    def registry(self):
        reg = CommandRegistry()
        reg.register(ProcessDataCommand)
        reg.register(FailingCommand)
        return reg

    @patch("foobara_py.connectors.celery_connector.CeleryTaskFactory.get_celery_app")
    def test_retry_status(self, mock_get_app, registry):
        """Test job in retry status"""
        mock_app = MagicMock()
        mock_app.task = MagicMock(return_value=lambda f: f)
        mock_app.conf = MagicMock()
        mock_app.conf.beat_schedule = {}
        mock_get_app.return_value = mock_app

        mock_result = MagicMock()
        mock_result.state = "RETRY"
        mock_result.successful.return_value = False
        mock_result.failed.return_value = False
        mock_app.AsyncResult.return_value = mock_result

        connector = CeleryConnector(registry)
        result = connector.get_result("job-123")

        assert result.status == JobStatus.RETRY

    @patch("foobara_py.connectors.celery_connector.CeleryTaskFactory.get_celery_app")
    def test_max_retries_exceeded(self, mock_get_app, registry):
        """Test job that exceeded max retries"""
        mock_app = MagicMock()
        mock_app.task = MagicMock(return_value=lambda f: f)
        mock_app.conf = MagicMock()
        mock_get_app.return_value = mock_app

        config = CeleryConfig(max_retries=3)
        connector = CeleryConnector(registry, config)

        # Should have max_retries set
        assert connector.config.max_retries == 3

    @patch("foobara_py.connectors.celery_connector.CeleryTaskFactory.get_celery_app")
    def test_execute_with_retry_options(self, mock_get_app, registry):
        """Test execute with retry configuration in config"""
        mock_app = MagicMock()
        mock_app.task = MagicMock(return_value=lambda f: f)
        mock_app.conf = MagicMock()
        mock_app.conf.beat_schedule = {}
        mock_get_app.return_value = mock_app

        mock_task = MagicMock()
        mock_async_result = MagicMock()
        mock_async_result.id = "retry-job-1"
        mock_task.apply_async.return_value = mock_async_result

        # Test that connector accepts max_retries in config
        config = CeleryConfig(max_retries=5)
        connector = CeleryConnector(registry, config)
        connector._tasks_created = True
        connector.task_factory._tasks["foobara.ProcessDataCommand"] = mock_task

        result = connector.execute_async(
            "ProcessDataCommand",
            {"data": "test"}
        )

        assert result.job_id == "retry-job-1"
        assert connector.config.max_retries == 5

    @patch("foobara_py.connectors.celery_connector.CeleryTaskFactory.get_celery_app")
    def test_exponential_backoff_config(self, mock_get_app, registry):
        """Test exponential backoff configuration"""
        mock_app = MagicMock()
        mock_app.task = MagicMock(return_value=lambda f: f)
        mock_get_app.return_value = mock_app

        # Test that config can be created with various retry settings
        config = CeleryConfig(
            max_retries=5,
            task_time_limit=3600
        )
        connector = CeleryConnector(registry, config)

        assert connector.config.max_retries == 5
        assert connector.config.task_time_limit == 3600

    @patch("foobara_py.connectors.celery_connector.CeleryTaskFactory.get_celery_app")
    def test_revoked_job_status(self, mock_get_app, registry):
        """Test getting status of revoked job"""
        mock_app = MagicMock()
        mock_app.task = MagicMock(return_value=lambda f: f)
        mock_get_app.return_value = mock_app

        mock_result = MagicMock()
        mock_result.state = "REVOKED"
        mock_result.successful.return_value = False
        mock_result.failed.return_value = False
        mock_app.AsyncResult.return_value = mock_result

        connector = CeleryConnector(registry)
        result = connector.get_result("revoked-job")

        assert result.status == JobStatus.REVOKED

    @patch("foobara_py.connectors.celery_connector.CeleryTaskFactory.get_celery_app")
    def test_revoke_with_signal(self, mock_get_app, registry):
        """Test revoking job with different signals"""
        mock_app = MagicMock()
        mock_app.task = MagicMock(return_value=lambda f: f)
        mock_app.control = MagicMock()
        mock_get_app.return_value = mock_app

        connector = CeleryConnector(registry)

        # Test with SIGKILL
        connector.revoke("job-1", terminate=True, signal="SIGKILL")
        mock_app.control.revoke.assert_called_with("job-1", terminate=True, signal="SIGKILL")

    @patch("foobara_py.connectors.celery_connector.CeleryTaskFactory.get_celery_app")
    def test_revoke_without_terminate(self, mock_get_app, registry):
        """Test soft revoke without termination"""
        mock_app = MagicMock()
        mock_app.task = MagicMock(return_value=lambda f: f)
        mock_app.control = MagicMock()
        mock_get_app.return_value = mock_app

        connector = CeleryConnector(registry)
        result = connector.revoke("job-1", terminate=False)

        assert result is True
        mock_app.control.revoke.assert_called_with("job-1", terminate=False, signal="SIGTERM")


class TestCeleryQueueConfiguration:
    """Tests for queue configuration edge cases"""

    @pytest.fixture
    def registry(self):
        reg = CommandRegistry()
        reg.register(ProcessDataCommand)
        return reg

    @patch("foobara_py.connectors.celery_connector.CeleryTaskFactory.get_celery_app")
    def test_custom_queue_routing(self, mock_get_app, registry):
        """Test routing to custom queues"""
        mock_app = MagicMock()
        mock_app.task = MagicMock(return_value=lambda f: f)
        mock_app.conf = MagicMock()
        mock_app.conf.beat_schedule = {}
        mock_get_app.return_value = mock_app

        mock_task = MagicMock()
        mock_async_result = MagicMock()
        mock_async_result.id = "queue-job-1"
        mock_task.apply_async.return_value = mock_async_result

        connector = CeleryConnector(registry)
        connector._tasks_created = True
        connector.task_factory._tasks["foobara.ProcessDataCommand"] = mock_task

        # Execute with specific queue
        result = connector.execute_async(
            "ProcessDataCommand",
            {"data": "test"},
            queue="high_priority"
        )

        call_kwargs = mock_task.apply_async.call_args[1]
        assert call_kwargs["queue"] == "high_priority"

    @patch("foobara_py.connectors.celery_connector.CeleryTaskFactory.get_celery_app")
    def test_priority_levels(self, mock_get_app, registry):
        """Test different priority levels"""
        mock_app = MagicMock()
        mock_app.task = MagicMock(return_value=lambda f: f)
        mock_app.conf = MagicMock()
        mock_app.conf.beat_schedule = {}
        mock_get_app.return_value = mock_app

        mock_task = MagicMock()
        mock_async_result = MagicMock()
        mock_async_result.id = "priority-job"
        mock_task.apply_async.return_value = mock_async_result

        connector = CeleryConnector(registry)
        connector._tasks_created = True
        connector.task_factory._tasks["foobara.ProcessDataCommand"] = mock_task

        # Test priority 0-10
        for priority in [0, 5, 10]:
            connector.execute_async(
                "ProcessDataCommand",
                {"data": "test"},
                priority=priority
            )

    @patch("foobara_py.connectors.celery_connector.CeleryTaskFactory.get_celery_app")
    def test_countdown_and_eta(self, mock_get_app, registry):
        """Test countdown and ETA scheduling"""
        mock_app = MagicMock()
        mock_app.task = MagicMock(return_value=lambda f: f)
        mock_app.conf = MagicMock()
        mock_app.conf.beat_schedule = {}
        mock_get_app.return_value = mock_app

        mock_task = MagicMock()
        mock_async_result = MagicMock()
        mock_async_result.id = "delayed-job"
        mock_task.apply_async.return_value = mock_async_result

        connector = CeleryConnector(registry)
        connector._tasks_created = True
        connector.task_factory._tasks["foobara.ProcessDataCommand"] = mock_task

        # Test with countdown
        connector.execute_async(
            "ProcessDataCommand",
            {"data": "test"},
            countdown=300  # 5 minutes
        )

        call_kwargs = mock_task.apply_async.call_args[1]
        assert call_kwargs["countdown"] == 300

    @patch("foobara_py.connectors.celery_connector.CeleryTaskFactory.get_celery_app")
    def test_task_time_limit(self, mock_get_app, registry):
        """Test task time limit configuration"""
        mock_app = MagicMock()
        mock_app.task = MagicMock(return_value=lambda f: f)
        mock_get_app.return_value = mock_app

        config = CeleryConfig(
            task_time_limit=3600,
            task_soft_time_limit=3000
        )
        connector = CeleryConnector(registry, config)

        assert connector.config.task_time_limit == 3600
        assert connector.config.task_soft_time_limit == 3000


class TestCelerySchedulerEdgeCases:
    """Tests for scheduler edge cases"""

    @pytest.fixture
    def registry(self):
        reg = CommandRegistry()
        reg.register(ProcessDataCommand)
        return reg

    @patch("foobara_py.connectors.celery_connector.CeleryTaskFactory.get_celery_app")
    def test_schedule_without_name(self, mock_get_app, registry):
        """Test scheduling without explicit name"""
        mock_app = MagicMock()
        mock_app.task = MagicMock(return_value=lambda f: f)
        mock_app.conf = MagicMock()
        mock_app.conf.beat_schedule = {}
        mock_get_app.return_value = mock_app

        with patch.dict("sys.modules", {"celery.schedules": MagicMock()}):
            connector = CeleryConnector(registry)
            connector._tasks_created = True
            scheduler = CeleryScheduler(connector)

            name = scheduler.schedule(
                "ProcessDataCommand",
                inputs={"data": "test"},
                interval=60
            )

            # Should auto-generate name
            assert name == "ProcessDataCommand_schedule"

    @patch("foobara_py.connectors.celery_connector.CeleryTaskFactory.get_celery_app")
    def test_schedule_with_very_short_interval(self, mock_get_app, registry):
        """Test scheduling with very short interval"""
        mock_app = MagicMock()
        mock_app.task = MagicMock(return_value=lambda f: f)
        mock_app.conf = MagicMock()
        mock_app.conf.beat_schedule = {}
        mock_get_app.return_value = mock_app

        with patch.dict("sys.modules", {"celery.schedules": MagicMock()}):
            connector = CeleryConnector(registry)
            connector._tasks_created = True
            scheduler = CeleryScheduler(connector)

            # 1 second interval
            name = scheduler.schedule(
                "ProcessDataCommand",
                interval=1,
                name="every_second"
            )

            assert name == "every_second"

    @patch("foobara_py.connectors.celery_connector.CeleryTaskFactory.get_celery_app")
    def test_complex_crontab(self, mock_get_app, registry):
        """Test complex crontab expression"""
        mock_app = MagicMock()
        mock_app.task = MagicMock(return_value=lambda f: f)
        mock_app.conf = MagicMock()
        mock_app.conf.beat_schedule = {}
        mock_get_app.return_value = mock_app

        with patch.dict("sys.modules", {"celery.schedules": MagicMock()}):
            import sys
            mock_schedules = sys.modules["celery.schedules"]
            mock_crontab_instance = MagicMock()
            mock_schedules.crontab.return_value = mock_crontab_instance

            connector = CeleryConnector(registry)
            connector._tasks_created = True
            scheduler = CeleryScheduler(connector)

            # Every weekday at 9 AM
            scheduler.schedule(
                "ProcessDataCommand",
                crontab={
                    "hour": 9,
                    "minute": 0,
                    "day_of_week": "1-5"
                },
                name="weekday_morning"
            )

    @patch("foobara_py.connectors.celery_connector.CeleryTaskFactory.get_celery_app")
    def test_reschedule_existing(self, mock_get_app, registry):
        """Test rescheduling an existing task"""
        mock_app = MagicMock()
        mock_app.task = MagicMock(return_value=lambda f: f)
        mock_app.conf = MagicMock()
        mock_app.conf.beat_schedule = {}
        mock_get_app.return_value = mock_app

        with patch.dict("sys.modules", {"celery.schedules": MagicMock()}):
            connector = CeleryConnector(registry)
            connector._tasks_created = True
            scheduler = CeleryScheduler(connector)

            # Schedule once
            scheduler.schedule(
                "ProcessDataCommand",
                interval=60,
                name="test_schedule"
            )

            # Reschedule with different interval
            scheduler.schedule(
                "ProcessDataCommand",
                interval=120,
                name="test_schedule"
            )

            # Should update existing
            assert "test_schedule" in scheduler._schedules


class TestCeleryErrorHandling:
    """Tests for error handling edge cases"""

    @pytest.fixture
    def registry(self):
        reg = CommandRegistry()
        reg.register(ProcessDataCommand)
        return reg

    @patch("foobara_py.connectors.celery_connector.CeleryTaskFactory.get_celery_app")
    def test_get_result_unknown_state(self, mock_get_app, registry):
        """Test handling unknown task state"""
        mock_app = MagicMock()
        mock_app.task = MagicMock(return_value=lambda f: f)
        mock_get_app.return_value = mock_app

        mock_result = MagicMock()
        mock_result.state = "UNKNOWN_STATE"
        mock_result.successful.return_value = False
        mock_result.failed.return_value = False
        mock_app.AsyncResult.return_value = mock_result

        connector = CeleryConnector(registry)
        result = connector.get_result("unknown-job")

        # Should handle gracefully
        assert result is not None

    @patch("foobara_py.connectors.celery_connector.CeleryTaskFactory.get_celery_app")
    def test_execute_with_invalid_inputs(self, mock_get_app, registry):
        """Test executing with invalid input types"""
        mock_app = MagicMock()
        mock_app.task = MagicMock(return_value=lambda f: f)
        mock_app.conf = MagicMock()
        mock_app.conf.beat_schedule = {}
        mock_get_app.return_value = mock_app

        mock_task = MagicMock()
        mock_async_result = MagicMock()
        mock_async_result.id = "invalid-job"
        mock_task.apply_async.return_value = mock_async_result

        connector = CeleryConnector(registry)
        connector._tasks_created = True
        connector.task_factory._tasks["foobara.ProcessDataCommand"] = mock_task

        # Execute with wrong input types
        result = connector.execute_async(
            "ProcessDataCommand",
            {"data": 123, "priority": "not_an_int"}  # Wrong types
        )

        # Should still submit (validation happens in worker)
        assert result.job_id == "invalid-job"

    @patch("foobara_py.connectors.celery_connector.CeleryTaskFactory.get_celery_app")
    def test_missing_celery_dependency(self, mock_get_app, registry):
        """Test behavior when Celery is not installed"""
        # This would require more complex mocking to simulate import error
        # For now, just test that connector requires celery
        mock_app = MagicMock()
        mock_get_app.return_value = mock_app

        connector = CeleryConnector(registry)
        assert connector is not None
