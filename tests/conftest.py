from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def load_ics(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture
def event_meeting_ics():
    return load_ics("event_meeting.ics")


@pytest.fixture
def event_allday_ics():
    return load_ics("event_allday.ics")


@pytest.fixture
def task_open_ics():
    return load_ics("task_open.ics")


@pytest.fixture
def task_done_ics():
    return load_ics("task_done.ics")
