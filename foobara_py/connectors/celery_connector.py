"""
Celery Connector for Foobara commands.

Provides async job execution for Foobara commands using Celery,
similar to Ruby's Resque connector.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, Union

from pydantic import BaseModel

from foobara_py.core.command import Command
from foobara_py.core.registry import CommandRegistry


class JobStatus(Enum):
    """Job execution status."""

    PENDING = "pending"
    STARTED = "started"
    SUCCESS = "success"
    FAILURE = "failure"
    REVOKED = "revoked"
    RETRY = "retry"


@dataclass
class JobResult:
    """Result of an async job execution."""

    job_id: str
    status: JobStatus
    command_name: str
    inputs: Dict[str, Any]
    result: Optional[Any] = None
    error: Optional[str] = None
    traceback: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retries: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "job_id": self.job_id,
            "status": self.status.value,
            "command_name": self.command_name,
            "inputs": self.inputs,
            "result": self.result,
            "error": self.error,
            "traceback": self.traceback,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "retries": self.retries,
        }


@dataclass
class CeleryConfig:
    """Configuration for Celery connector."""

    # Celery broker URL
    broker_url: str = "redis://localhost:6379/0"

    # Result backend URL
    result_backend: str = "redis://localhost:6379/0"

    # Default queue name
    default_queue: str = "foobara"

    # Task serializer
    task_serializer: str = "json"

    # Result serializer
    result_serializer: str = "json"

    # Accept content types
    accept_content: List[str] = field(default_factory=lambda: ["json"])

    # Task time limit (seconds)
    task_time_limit: int = 3600  # 1 hour

    # Soft time limit (seconds)
    task_soft_time_limit: int = 3000

    # Max retries
    max_retries: int = 3

    # Retry delay (seconds)
    retry_delay: int = 60

    # Enable task events
    task_send_sent_event: bool = True

    # Task acknowledgement
    task_acks_late: bool = True

    # Worker prefetch multiplier
    worker_prefetch_multiplier: int = 1


@dataclass
class ScheduleConfig:
    """Configuration for scheduled tasks."""

    # Crontab schedule (minute, hour, day_of_week, day_of_month, month_of_year)
    crontab: Optional[Dict[str, Any]] = None

    # Interval schedule (every X seconds)
    interval: Optional[float] = None

    # Solar schedule
    solar: Optional[Dict[str, Any]] = None

    # Command inputs
    inputs: Dict[str, Any] = field(default_factory=dict)

    # Task options
    options: Dict[str, Any] = field(default_factory=dict)


class CeleryTaskFactory:
    """Factory for creating Celery tasks from Foobara commands.

    This class creates Celery task wrappers for Foobara commands,
    allowing them to be executed asynchronously.
    """

    def __init__(
        self,
        registry: Optional[CommandRegistry] = None,
        config: Optional[CeleryConfig] = None,
    ):
        """Initialize the task factory.

        Args:
            registry: Command registry to use.
            config: Celery configuration.
        """
        self.registry = registry or CommandRegistry()
        self.config = config or CeleryConfig()
        self._tasks: Dict[str, Callable] = {}
        self._celery_app = None

    def get_celery_app(self):
        """Get or create the Celery application.

        Returns:
            Celery application instance.

        Raises:
            ImportError: If Celery is not installed.
        """
        if self._celery_app is not None:
            return self._celery_app

        try:
            from celery import Celery
        except ImportError:
            raise ImportError(
                "Celery is required for the Celery connector. "
                "Install it with: pip install celery[redis]"
            )

        self._celery_app = Celery(
            "foobara",
            broker=self.config.broker_url,
            backend=self.config.result_backend,
        )

        # Apply configuration
        self._celery_app.conf.update(
            task_serializer=self.config.task_serializer,
            result_serializer=self.config.result_serializer,
            accept_content=self.config.accept_content,
            task_time_limit=self.config.task_time_limit,
            task_soft_time_limit=self.config.task_soft_time_limit,
            task_acks_late=self.config.task_acks_late,
            worker_prefetch_multiplier=self.config.worker_prefetch_multiplier,
            task_send_sent_event=self.config.task_send_sent_event,
            task_default_queue=self.config.default_queue,
        )

        return self._celery_app

    def create_task(
        self,
        command_class: Type[Command],
        name: Optional[str] = None,
        queue: Optional[str] = None,
        max_retries: Optional[int] = None,
    ) -> Callable:
        """Create a Celery task for a command.

        Args:
            command_class: The command class to wrap.
            name: Optional task name. Defaults to command class name.
            queue: Optional queue name. Defaults to config default.
            max_retries: Optional max retries. Defaults to config value.

        Returns:
            Celery task function.
        """
        app = self.get_celery_app()
        task_name = name or f"foobara.{command_class.__name__}"
        task_queue = queue or self.config.default_queue
        task_max_retries = max_retries if max_retries is not None else self.config.max_retries

        @app.task(
            name=task_name,
            bind=True,
            max_retries=task_max_retries,
            default_retry_delay=self.config.retry_delay,
            queue=task_queue,
        )
        def execute_command(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
            """Execute the Foobara command.

            Args:
                inputs: Command inputs.

            Returns:
                Command result or error information.
            """
            try:
                outcome = command_class.run(**inputs)

                if outcome.is_success():
                    result = outcome.result
                    if isinstance(result, BaseModel):
                        result = result.model_dump()
                    return {
                        "status": "success",
                        "result": result,
                    }
                else:
                    return {
                        "status": "failure",
                        "errors": [
                            {
                                "key": str(getattr(err, "symbol", "error")),
                                "message": str(err),
                            }
                            for err in (outcome.errors or [])
                        ],
                    }
            except Exception as exc:
                # Retry on transient errors
                raise self.retry(exc=exc)

        self._tasks[task_name] = execute_command
        return execute_command

    def create_all_tasks(self) -> Dict[str, Callable]:
        """Create Celery tasks for all registered commands.

        Returns:
            Dictionary mapping task names to task functions.
        """
        for command_class in self.registry.list_commands():
            self.create_task(command_class)
        return self._tasks

    def get_task(self, name: str) -> Optional[Callable]:
        """Get a task by name.

        Args:
            name: Task name.

        Returns:
            Task function or None if not found.
        """
        return self._tasks.get(name)


class CeleryConnector:
    """Celery connector for Foobara commands.

    Provides async job execution capabilities for Foobara commands
    using Celery as the task queue.

    Example:
        from foobara_py.connectors.celery_connector import CeleryConnector

        connector = CeleryConnector(registry)

        # Execute command asynchronously
        job = connector.execute_async("CreateUser", {"name": "John"})
        print(f"Job ID: {job.job_id}")

        # Check job status
        result = connector.get_result(job.job_id)
        print(f"Status: {result.status}")
    """

    def __init__(
        self,
        registry: Optional[CommandRegistry] = None,
        config: Optional[CeleryConfig] = None,
    ):
        """Initialize the Celery connector.

        Args:
            registry: Command registry to use.
            config: Celery configuration.
        """
        self.registry = registry or CommandRegistry()
        self.config = config or CeleryConfig()
        self.task_factory = CeleryTaskFactory(registry, config)
        self._tasks_created = False

    def _ensure_tasks(self):
        """Ensure all tasks are created."""
        if not self._tasks_created:
            self.task_factory.create_all_tasks()
            self._tasks_created = True

    def execute_async(
        self,
        command_name: str,
        inputs: Dict[str, Any],
        queue: Optional[str] = None,
        countdown: Optional[int] = None,
        eta: Optional[datetime] = None,
        expires: Optional[Union[int, datetime]] = None,
        priority: Optional[int] = None,
    ) -> JobResult:
        """Execute a command asynchronously.

        Args:
            command_name: Name of the command to execute.
            inputs: Command inputs.
            queue: Optional queue name.
            countdown: Execute after X seconds.
            eta: Execute at specific time.
            expires: Task expiration time.
            priority: Task priority (0-9, higher = more important).

        Returns:
            JobResult with job ID and initial status.

        Raises:
            ValueError: If command not found.
        """
        self._ensure_tasks()

        task_name = f"foobara.{command_name}"
        task = self.task_factory.get_task(task_name)

        if not task:
            # Try to find command and create task on demand
            command_class = self.registry.get(command_name)
            if not command_class:
                raise ValueError(f"Command not found: {command_name}")
            task = self.task_factory.create_task(command_class)

        # Apply task
        apply_kwargs = {}
        if queue:
            apply_kwargs["queue"] = queue
        if countdown:
            apply_kwargs["countdown"] = countdown
        if eta:
            apply_kwargs["eta"] = eta
        if expires:
            apply_kwargs["expires"] = expires
        if priority is not None:
            apply_kwargs["priority"] = priority

        async_result = task.apply_async(args=[inputs], **apply_kwargs)

        return JobResult(
            job_id=async_result.id,
            status=JobStatus.PENDING,
            command_name=command_name,
            inputs=inputs,
        )

    def get_result(self, job_id: str) -> JobResult:
        """Get the result of an async job.

        Args:
            job_id: The job ID.

        Returns:
            JobResult with current status and result.
        """
        app = self.task_factory.get_celery_app()
        async_result = app.AsyncResult(job_id)

        # Map Celery state to JobStatus
        status_map = {
            "PENDING": JobStatus.PENDING,
            "STARTED": JobStatus.STARTED,
            "SUCCESS": JobStatus.SUCCESS,
            "FAILURE": JobStatus.FAILURE,
            "REVOKED": JobStatus.REVOKED,
            "RETRY": JobStatus.RETRY,
        }

        status = status_map.get(async_result.state, JobStatus.PENDING)

        result = None
        error = None
        traceback = None

        if async_result.successful():
            result = async_result.result
        elif async_result.failed():
            error = str(async_result.result)
            traceback = async_result.traceback

        return JobResult(
            job_id=job_id,
            status=status,
            command_name="",  # Not stored in result
            inputs={},
            result=result,
            error=error,
            traceback=traceback,
        )

    def revoke(
        self,
        job_id: str,
        terminate: bool = False,
        signal: str = "SIGTERM",
    ) -> bool:
        """Revoke/cancel a job.

        Args:
            job_id: The job ID to revoke.
            terminate: Whether to terminate running task.
            signal: Signal to send if terminating.

        Returns:
            True if revocation was sent.
        """
        app = self.task_factory.get_celery_app()
        app.control.revoke(job_id, terminate=terminate, signal=signal)
        return True

    def get_celery_app(self):
        """Get the Celery application instance.

        Returns:
            Celery application.
        """
        return self.task_factory.get_celery_app()


class CeleryScheduler:
    """Scheduler for periodic Foobara command execution.

    Integrates with Celery Beat for scheduled task execution.

    Example:
        scheduler = CeleryScheduler(connector)

        # Schedule command to run every hour
        scheduler.schedule(
            "CleanupExpiredSessions",
            interval=3600,
        )

        # Schedule command with crontab
        scheduler.schedule(
            "GenerateDailyReport",
            crontab={"hour": 0, "minute": 0},
        )
    """

    def __init__(self, connector: CeleryConnector):
        """Initialize the scheduler.

        Args:
            connector: Celery connector instance.
        """
        self.connector = connector
        self._schedules: Dict[str, ScheduleConfig] = {}

    def schedule(
        self,
        command_name: str,
        inputs: Optional[Dict[str, Any]] = None,
        interval: Optional[float] = None,
        crontab: Optional[Dict[str, Any]] = None,
        name: Optional[str] = None,
        **options,
    ) -> str:
        """Schedule a command for periodic execution.

        Args:
            command_name: Name of the command to schedule.
            inputs: Command inputs.
            interval: Run every X seconds.
            crontab: Crontab schedule dict with keys:
                     minute, hour, day_of_week, day_of_month, month_of_year
            name: Optional schedule name.
            **options: Additional Celery task options.

        Returns:
            Schedule name/ID.

        Raises:
            ValueError: If neither interval nor crontab provided.
        """
        if not interval and not crontab:
            raise ValueError("Either interval or crontab must be provided")

        schedule_name = name or f"{command_name}_schedule"
        config = ScheduleConfig(
            crontab=crontab,
            interval=interval,
            inputs=inputs or {},
            options=options,
        )

        self._schedules[schedule_name] = config

        # Add to Celery Beat schedule
        app = self.connector.get_celery_app()
        task_name = f"foobara.{command_name}"

        try:
            from celery.schedules import crontab as celery_crontab
        except ImportError:
            raise ImportError("Celery is required for scheduling")

        if interval:
            schedule = interval
        else:
            schedule = celery_crontab(**crontab)

        app.conf.beat_schedule[schedule_name] = {
            "task": task_name,
            "schedule": schedule,
            "args": [config.inputs],
            "options": config.options,
        }

        return schedule_name

    def unschedule(self, schedule_name: str) -> bool:
        """Remove a scheduled task.

        Args:
            schedule_name: Name of the schedule to remove.

        Returns:
            True if schedule was removed.
        """
        if schedule_name in self._schedules:
            del self._schedules[schedule_name]

            app = self.connector.get_celery_app()
            if schedule_name in app.conf.beat_schedule:
                del app.conf.beat_schedule[schedule_name]
            return True
        return False

    def list_schedules(self) -> Dict[str, ScheduleConfig]:
        """List all scheduled tasks.

        Returns:
            Dictionary of schedule names to configurations.
        """
        return self._schedules.copy()


# Convenience functions
def create_celery_app(
    registry: Optional[CommandRegistry] = None,
    config: Optional[CeleryConfig] = None,
) -> Any:
    """Create a Celery app with all commands registered as tasks.

    Args:
        registry: Command registry.
        config: Celery configuration.

    Returns:
        Configured Celery application.

    Example:
        app = create_celery_app(registry)

        # Run worker
        # celery -A myapp worker --loglevel=info
    """
    connector = CeleryConnector(registry, config)
    connector._ensure_tasks()
    return connector.get_celery_app()


def execute_async(
    command_name: str,
    inputs: Dict[str, Any],
    registry: Optional[CommandRegistry] = None,
    config: Optional[CeleryConfig] = None,
    **kwargs,
) -> JobResult:
    """Execute a command asynchronously.

    Args:
        command_name: Name of the command.
        inputs: Command inputs.
        registry: Optional command registry.
        config: Optional Celery configuration.
        **kwargs: Additional options (queue, countdown, etc.)

    Returns:
        JobResult with job ID.
    """
    connector = CeleryConnector(registry, config)
    return connector.execute_async(command_name, inputs, **kwargs)
