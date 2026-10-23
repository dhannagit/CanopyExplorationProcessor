"""Shared resource folder preferences."""

from PySide6.QtWidgets import (
	QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout,
	QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from .settings import validate_resource_directory


class SettingsDialog(QDialog):
	def __init__(self, resource_directory: str, parent: QWidget | None = None) -> None:
		super().__init__(parent)
		self.setWindowTitle("Settings")
		self.resize(640, 160)
		layout = QVBoxLayout(self)
		form = QFormLayout()
		folder_row = QHBoxLayout()
		self.directory_edit = QLineEdit(resource_directory)
		browse = QPushButton("Browse...")
		browse.clicked.connect(self._browse)
		folder_row.addWidget(self.directory_edit, 1)
		folder_row.addWidget(browse)
		form.addRow("Circuit resource folder:", folder_row)
		layout.addLayout(form)
		self.error_label = QLabel()
		self.error_label.setWordWrap(True)
		layout.addWidget(self.error_label)
		buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
		buttons.accepted.connect(self.accept)
		buttons.rejected.connect(self.reject)
		layout.addWidget(buttons)

	@property
	def resource_directory(self) -> str:
		return self.directory_edit.text().strip()

	def _browse(self) -> None:
		directory = QFileDialog.getExistingDirectory(self, "Select synced circuit resource folder", self.resource_directory)
		if directory:
			self.directory_edit.setText(directory)

	def accept(self) -> None:
		try:
			validate_resource_directory(self.resource_directory)
		except Exception as error:
			self.error_label.setText(f"Cannot read circuit workbook: {error}")
			return
		super().accept()