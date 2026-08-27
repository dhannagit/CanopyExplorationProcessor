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