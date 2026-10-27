import pytest

from canopy_processor.ui import AnalysisSession, SessionState


def test_session_requires_review_before_analysis() -> None:
	session = AnalysisSession()
	session.begin_discovery()
	session.finish_discovery(("pressure",))

	assert session.state is SessionState.REVIEW_REQUIRED
	session.mark_ready()
	session.begin_analysis()

	assert session.state is SessionState.ANALYZING


def test_failed_analysis_preserves_last_valid_result() -> None:
	session = AnalysisSession(state=SessionState.READY, result={"value": 1})
	session.begin_analysis()
	session.fail("load failed")

	assert session.state is SessionState.FAILED
	assert session.result == {"value": 1}
	assert session.last_error == "load failed"


def test_cancellation_does_not_discard_result() -> None:
	session = AnalysisSession(state=SessionState.READY, result="previous")
	session.begin_analysis()
	session.request_cancel()

	assert session.state is SessionState.CANCELLING
	assert session.has_results


def test_discovery_cancellation_returns_to_empty() -> None:
	session = AnalysisSession()
	session.begin_discovery()
	session.request_cancel()
	session.complete_cancellation()

	assert session.state is SessionState.EMPTY


@pytest.mark.parametrize("state", [SessionState.RESULTS_AVAILABLE, SessionState.FAILED])
def test_variables_can_be_reconfirmed_in_idle_session(state: SessionState) -> None:
	session = AnalysisSession(state=state, discovery_result="study", result="last result", last_error="old error")
	session.mark_ready()
	assert session.state is SessionState.READY
	assert session.result == "last result"
	assert session.last_error is None


@pytest.mark.parametrize("state", [
	SessionState.EMPTY, SessionState.DISCOVERING, SessionState.LOADING,
	SessionState.ANALYZING, SessionState.CANCELLING,
])
def test_reconfirmation_rejects_uninitialized_or_busy_session(state: SessionState) -> None:
	session = AnalysisSession(state=state)
	with pytest.raises(RuntimeError, match="reviewed first"):
		session.mark_ready()
	assert session.state is state