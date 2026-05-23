from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
import queue
import threading
import time
import traceback
import uuid
from typing import Any, Callable


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELING = "canceling"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


TERMINAL_STATUSES = {
    TaskStatus.COMPLETED,
    TaskStatus.FAILED,
    TaskStatus.CANCELED,
}


_ALLOWED_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING: {TaskStatus.RUNNING, TaskStatus.CANCELED, TaskStatus.FAILED},
    TaskStatus.RUNNING: {TaskStatus.CANCEL_REQUESTED, TaskStatus.COMPLETED, TaskStatus.FAILED},
    TaskStatus.CANCEL_REQUESTED: {TaskStatus.CANCELING, TaskStatus.CANCELED, TaskStatus.FAILED},
    TaskStatus.CANCELING: {TaskStatus.CANCELED, TaskStatus.FAILED},
    TaskStatus.COMPLETED: set(),
    TaskStatus.FAILED: set(),
    TaskStatus.CANCELED: set(),
}


@dataclass
class TaskError:
    message: str
    exception_type: str = ""
    traceback: str = ""

    @classmethod
    def from_exception(cls, exc: BaseException) -> "TaskError":
        return cls(
            message=str(exc),
            exception_type=type(exc).__name__,
            traceback=traceback.format_exc(limit=8),
        )


@dataclass
class ProgressEvent:
    task_id: int
    run_id: str
    done: float
    total: int
    detail: str = ""
    created_at: float = field(default_factory=time.monotonic)


@dataclass
class TaskRecord:
    task_id: int
    run_id: str
    kind: str
    name: str
    total: int = 1
    done: float = 0.0
    status: TaskStatus = TaskStatus.PENDING
    cancel_event: threading.Event | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    progress_events: list[ProgressEvent] = field(default_factory=list)
    ui_callbacks: queue.SimpleQueue[Callable[[], Any]] = field(default_factory=queue.SimpleQueue)
    future: Future | None = None
    started_at: float = 0.0
    finished_at: float = 0.0
    error: str | None = None
    wrapped_error: TaskError | None = None

    @property
    def is_active(self) -> bool:
        return self.status not in TERMINAL_STATUSES

    @property
    def cancel_requested(self) -> bool:
        if self.status in {TaskStatus.CANCEL_REQUESTED, TaskStatus.CANCELING, TaskStatus.CANCELED}:
            return True
        return bool(self.cancel_event is not None and self.cancel_event.is_set())


class TaskStateMachine:
    def __init__(self, record: TaskRecord) -> None:
        self.record = record

    def transition(self, status: TaskStatus, *, error: str | None = None) -> TaskRecord:
        current = self.record.status
        if status == current:
            return self.record
        if status not in _ALLOWED_TRANSITIONS[current]:
            raise ValueError(f"invalid task transition: {current.value} -> {status.value}")
        self.record.status = status
        if status == TaskStatus.RUNNING and not self.record.started_at:
            self.record.started_at = time.monotonic()
        if status in TERMINAL_STATUSES:
            self.record.finished_at = time.monotonic()
            self.record.error = error
        elif error is not None:
            self.record.error = error
        return self.record


class TaskManager:
    def __init__(
        self,
        *,
        ui_dispatch: Callable[[Callable[[], Any]], Any] | None = None,
        error_callback: Callable[[str], Any] | None = None,
        max_workers: int | None = None,
    ) -> None:
        self._lock = threading.RLock()
        self._next_id = 0
        self._records: dict[int, TaskRecord] = {}
        self._active_task_id: int | None = None
        self._ui_dispatch = ui_dispatch
        self._error_callback = error_callback
        self._executor = ThreadPoolExecutor(max_workers=max_workers or 4, thread_name_prefix="ShapeYourPhotoTask")

    def bind_ui_dispatcher(self, dispatch: Callable[[Callable[[], Any]], Any] | None) -> None:
        with self._lock:
            self._ui_dispatch = dispatch

    def bind_error_callback(self, callback: Callable[[str], Any] | None) -> None:
        with self._lock:
            self._error_callback = callback

    def create(
        self,
        *,
        kind: str,
        name: str,
        total: int = 1,
        run_id: str | int | None = None,
        cancel_event: threading.Event | None = None,
        metadata: dict[str, Any] | None = None,
        exclusive: bool = True,
    ) -> TaskRecord:
        with self._lock:
            active = self.active if exclusive else None
            if active is not None and active.is_active:
                raise RuntimeError(f"task already active: {active.kind}:{active.status.value}")
            self._next_id += 1
            if cancel_event is None:
                cancel_event = threading.Event()
            record = TaskRecord(
                task_id=self._next_id,
                run_id=str(run_id if run_id is not None else uuid.uuid4().hex),
                kind=kind,
                name=name,
                total=max(1, int(total)),
                cancel_event=cancel_event,
                metadata=dict(metadata or {}),
            )
            self._records[record.task_id] = record
            if exclusive:
                self._active_task_id = record.task_id
            return record

    def start(
        self,
        *,
        kind: str,
        name: str,
        total: int = 1,
        run_id: str | int | None = None,
        cancel_event: threading.Event | None = None,
        metadata: dict[str, Any] | None = None,
        exclusive: bool = True,
    ) -> TaskRecord:
        record = self.create(
            kind=kind,
            name=name,
            total=total,
            run_id=run_id,
            cancel_event=cancel_event,
            metadata=metadata,
            exclusive=exclusive,
        )
        with self._lock:
            TaskStateMachine(record).transition(TaskStatus.RUNNING)
        return record

    @property
    def active(self) -> TaskRecord | None:
        if self._active_task_id is None:
            return None
        return self._records.get(self._active_task_id)

    @property
    def is_busy(self) -> bool:
        active = self.active
        return bool(active is not None and active.is_active)

    def update_progress(self, *, done: float, total: int | None = None, task_id: int | None = None) -> TaskRecord | None:
        with self._lock:
            record = self._resolve(task_id)
            if record is None or not record.is_active:
                return record
            if total is not None:
                record.total = max(1, int(total))
            record.done = max(0.0, min(float(done), float(record.total)))
            record.progress_events.append(
                ProgressEvent(
                    task_id=record.task_id,
                    run_id=record.run_id,
                    done=record.done,
                    total=record.total,
                )
            )
            return record

    def request_cancel(self, task_id: int | None = None) -> TaskRecord | None:
        with self._lock:
            record = self._resolve(task_id)
            if record is None or record.status in TERMINAL_STATUSES:
                return record
            if record.cancel_event is not None:
                record.cancel_event.set()
            if record.status == TaskStatus.PENDING:
                return TaskStateMachine(record).transition(TaskStatus.CANCELED)
            if record.status == TaskStatus.RUNNING:
                return TaskStateMachine(record).transition(TaskStatus.CANCEL_REQUESTED)
            return record

    def mark_canceling(self, task_id: int | None = None) -> TaskRecord | None:
        with self._lock:
            record = self._resolve(task_id)
            if record is None:
                return None
            if record.status == TaskStatus.CANCEL_REQUESTED:
                return TaskStateMachine(record).transition(TaskStatus.CANCELING)
            return record

    def complete(self, task_id: int | None = None) -> TaskRecord | None:
        with self._lock:
            record = self._resolve(task_id)
            if record is None:
                return None
            if record.status in TERMINAL_STATUSES:
                return record
            TaskStateMachine(record).transition(TaskStatus.COMPLETED)
            self._clear_active_if(record)
            return record

    def fail(self, error: str, task_id: int | None = None) -> TaskRecord | None:
        with self._lock:
            record = self._resolve(task_id)
            if record is None:
                return None
            if record.status in TERMINAL_STATUSES:
                return record
            TaskStateMachine(record).transition(TaskStatus.FAILED, error=error)
            self._clear_active_if(record)
            return record

    def fail_with_exception(self, exc: BaseException, task_id: int | None = None) -> TaskRecord | None:
        wrapped = TaskError.from_exception(exc)
        record = self.fail(wrapped.message, task_id=task_id)
        if record is not None:
            record.wrapped_error = wrapped
        self._emit_error(f"{record.kind if record else 'task'} failed: {wrapped.message}")
        return record

    def cancel(self, task_id: int | None = None) -> TaskRecord | None:
        with self._lock:
            record = self._resolve(task_id)
            if record is None:
                return None
            if record.status in TERMINAL_STATUSES:
                return record
            if record.status == TaskStatus.RUNNING:
                TaskStateMachine(record).transition(TaskStatus.CANCEL_REQUESTED)
            if record.status == TaskStatus.CANCEL_REQUESTED:
                TaskStateMachine(record).transition(TaskStatus.CANCELING)
            if record.status == TaskStatus.CANCELING:
                TaskStateMachine(record).transition(TaskStatus.CANCELED)
            self._clear_active_if(record)
            return record

    def dispatch_ui(self, callback: Callable[[], Any], *, task_id: int | None = None) -> None:
        record = None
        with self._lock:
            record = self._resolve(task_id)
            if record is not None:
                record.ui_callbacks.put(callback)
        dispatch = self._ui_dispatch
        if dispatch is None:
            callback()
            return
        if record is None:
            dispatch(callback)
            return
        dispatch(lambda rid=record.task_id: self.drain_ui_callbacks(rid))

    def drain_ui_callbacks(self, task_id: int) -> int:
        record = self._records.get(task_id)
        if record is None:
            return 0
        drained = 0
        while True:
            try:
                callback = record.ui_callbacks.get_nowait()
            except queue.Empty:
                break
            try:
                callback()
            except Exception as exc:
                self._emit_error(f"ui callback failed: {exc}")
            drained += 1
        return drained

    def submit_worker(
        self,
        *,
        task_id: int | None,
        target: Callable[[], Any],
        on_done: Callable[[Any], Any] | None = None,
        on_error: Callable[[TaskError], Any] | None = None,
        on_finally: Callable[[], Any] | None = None,
    ) -> Future:
        record = self._resolve(task_id)
        resolved_task_id = record.task_id if record is not None else None

        def _runner() -> Any:
            try:
                if record is not None and record.status == TaskStatus.PENDING:
                    TaskStateMachine(record).transition(TaskStatus.RUNNING)
                result = target()
                if on_done is not None:
                    self.dispatch_ui(lambda r=result: on_done(r), task_id=resolved_task_id)
                return result
            except Exception as exc:
                wrapped = TaskError.from_exception(exc)
                if resolved_task_id is not None:
                    self.fail(wrapped.message, task_id=resolved_task_id)
                    resolved = self._resolve(resolved_task_id)
                    if resolved is not None:
                        resolved.wrapped_error = wrapped
                self._emit_error(f"task worker failed: {wrapped.message}")
                if on_error is not None:
                    self.dispatch_ui(lambda e=wrapped: on_error(e), task_id=resolved_task_id)
                raise
            finally:
                if on_finally is not None:
                    self.dispatch_ui(on_finally, task_id=resolved_task_id)

        future = self._executor.submit(_runner)
        if record is not None:
            with self._lock:
                record.future = future
        return future

    def submit(
        self,
        *,
        kind: str,
        name: str,
        target: Callable[[TaskRecord], Any],
        total: int = 1,
        run_id: str | int | None = None,
        cancel_event: threading.Event | None = None,
        metadata: dict[str, Any] | None = None,
        exclusive: bool = False,
        on_done: Callable[[Any], Any] | None = None,
        on_error: Callable[[TaskError], Any] | None = None,
    ) -> TaskRecord:
        record = self.create(
            kind=kind,
            name=name,
            total=total,
            run_id=run_id,
            cancel_event=cancel_event,
            metadata=metadata,
            exclusive=exclusive,
        )
        self.submit_worker(
            task_id=record.task_id,
            target=lambda rec=record: target(rec),
            on_done=on_done,
            on_error=on_error,
        )
        return record

    def worker_pool(self, *, max_workers: int, name_prefix: str = "ShapeYourPhotoWorker") -> ThreadPoolExecutor:
        return ThreadPoolExecutor(max_workers=max(1, int(max_workers)), thread_name_prefix=name_prefix)

    def snapshot(self) -> list[TaskRecord]:
        with self._lock:
            return list(self._records.values())

    def _resolve(self, task_id: int | None) -> TaskRecord | None:
        if task_id is None:
            return self.active
        return self._records.get(task_id)

    def _clear_active_if(self, record: TaskRecord) -> None:
        if self._active_task_id == record.task_id:
            self._active_task_id = None

    def _emit_error(self, message: str) -> None:
        callback = self._error_callback
        if callback is not None:
            try:
                callback(message)
            except Exception:
                pass
