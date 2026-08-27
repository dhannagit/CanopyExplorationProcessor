"""Framework-independent state model for one GUI analysis session."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..config import AnalysisConfig


class SessionState(str, Enum):
	"""Lifecycle states exposed by the GUI controller."""

	EMPTY = "empty"
	DISCOVERING = "discovering"
	REVIEW_REQUIRED = "review_required"
	READY = "ready"
	ANALYZING = "analyzing"
	CANCELLING = "cancelling"
	RESULTS_AVAILABLE = "results_available"
	FAILED = "failed"


@dataclass
class AnalysisSession:
	"""Mutable presentation state for a single analysis window.

	The numerical pipeline remains outside this model. Workers update this
	object at stage boundaries, while widgets observe its state and payloads.
	"""

	state: SessionState = SessionState.EMPTY
	config: AnalysisConfig = field(default_factory=AnalysisConfig)
	discovered_variables: tuple[Any, ...] = ()
	diagnostics: list[str] = field(default_factory=list)
	progress_stage: str | None = None
	progress_value: int = 0
	progress_total: int | None = None
	result: Any = None
	last_error: str | None = None

	@property
	def has_results(self) -> bool:
		"""Whether a valid result is available for the current window."""

		return self.result is not None

	def begin_discovery(self) -> None:
		"""Reset discovery payloads and enter the discovery state."""

		self.state = SessionState.DISCOVERING
		self.discovered_variables = ()
		self.diagnostics.clear()
		self.last_error = None

	def finish_discovery(self, variables: tuple[Any, ...], diagnostics: list[str] | None = None) -> None:
		"""Publish discovered candidates and require user review."""

		self.discovered_variables = variables
		self.diagnostics = list(diagnostics or [])
		self.state = SessionState.REVIEW_REQUIRED

	def mark_ready(self) -> None:
		"""Mark the reviewed configuration as ready to analyze."""

		if self.state not in {SessionState.REVIEW_REQUIRED, SessionState.READY}:
			raise RuntimeError("A discovered configuration must be reviewed first")
		self.state = SessionState.READY
		self.last_error = None

	def begin_analysis(self) -> None:
		"""Start an analysis while retaining any previous valid result."""

		if self.state not in {SessionState.READY, SessionState.RESULTS_AVAILABLE}:
			raise RuntimeError("The session is not ready to analyze")
		self.state = SessionState.ANALYZING
		self.progress_stage = None
		self.progress_value = 0
		self.progress_total = None
		self.last_error = None

	def request_cancel(self) -> None:
		"""Record a cancellation request without discarding current results."""

		if self.state == SessionState.ANALYZING:
			self.state = SessionState.CANCELLING

	def publish_result(self, result: Any) -> None:
		"""Publish a completed result and clear transient failure state."""

		self.result = result
		self.state = SessionState.RESULTS_AVAILABLE
		self.progress_stage = None
		self.last_error = None

	def fail(self, error: Exception | str) -> None:
		"""Expose an error while preserving the last valid result, if any."""

		self.state = SessionState.FAILED
		self.last_error = str(error)
		self.progress_stage = None

	def update_progress(self, stage: str, value: int, total: int | None = None) -> None:
		"""Update progress information for the status panel."""

		self.progress_stage = stage
		self.progress_value = value
		self.progress_total = total