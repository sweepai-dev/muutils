from muutils.logger.timing import TimerContext


def test_timer_context():
    with TimerContext() as timer:
        x: float = 1.0

    assert isinstance(timer.start_time, float)
    assert isinstance(timer.end_time, float)
    assert isinstance(timer.elapsed_time, float)
    assert timer.start_time <= timer.end_time
    assert timer.elapsed_time >= 0.0
