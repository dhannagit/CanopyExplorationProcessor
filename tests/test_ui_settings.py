import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from openpyxl import Workbook
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog

from canopy_processor.ui.settings import (
    RESOURCE_DIRECTORY_KEY,
    WORKBOOK_FILENAME,
    circuit_workbook,
    validate_resource_directory,
)
from canopy_processor.ui.settings_dialog import SettingsDialog
from canopy_processor.ui.main_window import MainWindow


@pytest.fixture
def application():
    return QApplication.instance() or QApplication([])


def write_workbook(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    workbook.active.title = "Turns"
    workbook.active.append(["Circuit", "Start", "End"])
    workbook.active.append(["CTMP", 0, 100])
    path = directory / WORKBOOK_FILENAME
    workbook.save(path)
    workbook.close()
    return path


def test_resource_directory_validation(tmp_path):
    assert circuit_workbook(" ") is None
    validate_resource_directory("")
    directory = tmp_path / "shared folder \u00e9"
    with pytest.raises(Exception):
        validate_resource_directory(str(directory))
    path = write_workbook(directory)
    assert circuit_workbook(str(directory)) == path
    validate_resource_directory(str(directory))
    path.write_bytes(b"invalid xlsx")
    with pytest.raises(Exception):
        validate_resource_directory(str(directory))


def test_application_logging_uses_user_directory(monkeypatch, tmp_path):
    import logging
    from canopy_processor.ui.app import configure_logging

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    logger = logging.getLogger("canopy_processor")
    before = list(logger.handlers)
    try:
        path = configure_logging()
        logger.info("startup check")
        assert path.is_relative_to(tmp_path)
        assert "startup check" in path.read_text(encoding="utf-8")
    finally:
        for handler in list(logger.handlers):
            if handler not in before:
                logger.removeHandler(handler)
                handler.close()


def test_settings_dialog_validates_and_browses(application, monkeypatch, tmp_path):
    dialog = SettingsDialog(str(tmp_path / "missing"))
    dialog.accept()
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert dialog.error_label.text()
    directory = tmp_path / "shared"
    write_workbook(directory)
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", lambda *args: str(directory)
    )
    dialog._browse()
    assert dialog.resource_directory == str(directory)
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Accepted
    dialog.close()


def test_empty_or_invalid_turns_sheet(tmp_path):
    workbook = Workbook()
    path = tmp_path / WORKBOOK_FILENAME
    workbook.save(path)
    with pytest.raises(KeyError):
        validate_resource_directory(str(tmp_path))
    workbook.active.title = "Turns"
    workbook.active.append(["Circuit"])
    workbook.save(path)
    workbook.close()
    with pytest.raises(ValueError, match="no circuit names"):
        validate_resource_directory(str(tmp_path))


def test_window_saves_only_accepted_settings(application, monkeypatch, tmp_path):
    settings_path = str(tmp_path / "settings.ini")
    settings = QSettings(settings_path, QSettings.Format.IniFormat)
    window = MainWindow(settings)
    assert window.menuBar().actions()[0].text() == "File"
    assert settings.value(RESOURCE_DIRECTORY_KEY, "") == ""
    directory = tmp_path / "shared"
    write_workbook(directory)

    def accept_dialog(dialog):
        dialog.directory_edit.setText(str(directory))
        dialog.accept()
        return dialog.result()

    monkeypatch.setattr(SettingsDialog, "exec", accept_dialog)
    window._open_settings()
    assert QSettings(settings_path, QSettings.Format.IniFormat).value(
        RESOURCE_DIRECTORY_KEY
    ) == str(directory)
    monkeypatch.setattr(
        SettingsDialog, "exec", lambda dialog: QDialog.DialogCode.Rejected
    )
    window._open_settings()
    assert settings.value(RESOURCE_DIRECTORY_KEY) == str(directory)
    window.close()


def test_discovery_snapshots_saved_resource_folder(application, monkeypatch, tmp_path):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    directory = tmp_path / "shared"
    workbook = write_workbook(directory)
    settings.setValue(RESOURCE_DIRECTORY_KEY, str(directory))
    window = MainWindow(settings)
    captured = []

    class Signal:
        def connect(self, callback):
            pass

    class Worker:
        progress = result_ready = failed = cancelled = Signal()

    class Thread:
        finished = Signal()

        def start(self):
            pass

    monkeypatch.setattr(
        "canopy_processor.ui.main_window.start_worker",
        lambda operation, **kwargs: captured.append(operation) or (Thread(), Worker()),
    )
    observed = []
    monkeypatch.setattr(
        "canopy_processor.ui.main_window.discover_dataset",
        lambda root, path: observed.append(path),
    )
    window._start_discovery(str(tmp_path))
    settings.setValue(RESOURCE_DIRECTORY_KEY, str(tmp_path / "different"))
    from canopy_processor.ui.worker import CancellationToken

    captured[0](CancellationToken(), lambda *args: None)
    assert observed == [workbook]
    window._thread = None
    window.close()
