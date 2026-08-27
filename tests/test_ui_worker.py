import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer

from canopy_processor.ui.worker import start_worker


def wait_for(signal, timeout: int = 2000) -> list:
	loop = QEventLoop()
	values: list = []
	signal.connect(lambda *args: (values.append(list(args)), loop.quit()))
	QTimer.singleShot(timeout, loop.quit)
	loop.exec()
	return values


def wait_for_thread(thread, timeout: int = 2000) -> None:
	loop = QEventLoop()
	thread.finished.connect(loop.quit)
	QTimer.singleShot(timeout, loop.quit)
	thread.start()
	loop.exec()


def test_worker_delivers_result() -> None:
	application = QCoreApplication.instance() or QCoreApplication([])
	thread, worker = start_worker(lambda token, progress: "complete", start=False)
	results = []
	worker.result_ready.connect(lambda value: (results.append(value)))
	wait_for_thread(thread)
	assert results == ["complete"]
	application.processEvents()


def test_worker_reports_cooperative_cancellation() -> None:
	application = QCoreApplication.instance() or QCoreApplication([])
	def operation(token, progress):
		progress("working", 1, 1)
		return "ignored after cancellation" if token.cancelled else "complete"

	thread, worker = start_worker(operation, start=False)
	cancelled: list[bool] = []
	worker.cancelled.connect(lambda: cancelled.append(True))
	worker.request_cancel()
	wait_for_thread(thread)
	assert cancelled == [True]
	application.processEvents()
