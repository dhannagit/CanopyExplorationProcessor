"""Cancellable Qt worker primitives for blocking analysis operations."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal, Slot


class CancellationToken:
	"""Thread-safe enough cooperative cancellation flag for one worker."""

	def __init__(self) -> None:
		self._cancelled = False

	@property
	def cancelled(self) -> bool:
		return self._cancelled

	def cancel(self) -> None:
		self._cancelled = True


class Worker(QObject):
	"""Execute a callable on a QThread and report lifecycle events."""

	progress = Signal(str, int, int)
	result_ready = Signal(object)
	failed = Signal(str)
	cancelled = Signal()
	finished = Signal()

	def __init__(self, operation: Callable[[CancellationToken, Callable[[str, int, int], None]], Any]) -> None:
		super().__init__()
		self._operation = operation
		self.token = CancellationToken()

	@Slot()
	def run(self) -> None:
		try:
			result = self._operation(self.token, self.progress.emit)
			if self.token.cancelled:
				self.cancelled.emit()
			else:
				self.result_ready.emit(result)
		except Exception as error:
			self.failed.emit(str(error))
		finally:
			self.finished.emit()

	def request_cancel(self) -> None:
		self.token.cancel()


def start_worker(
	operation: Callable[[CancellationToken, Callable[[str, int, int], None]], Any],
	*,
	start: bool = True,
) -> tuple[QThread, Worker]:
	"""Create a worker thread, optionally starting it immediately."""

	thread = QThread()
	worker = Worker(operation)
	worker.moveToThread(thread)
	thread.started.connect(worker.run)
	worker.finished.connect(thread.quit)
	worker.finished.connect(worker.deleteLater)
	thread.finished.connect(thread.deleteLater)
	if start:
		thread.start()
	return thread, worker