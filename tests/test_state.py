"""Tests for projectos/core/state.py."""
import pytest
from projectos.core.state import StateManager, VALID_TRANSITIONS
from projectos.core.models import Task


@pytest.fixture
def tmp_state(tmp_path):
    return StateManager(str(tmp_path))


class TestStateManager:
    def test_snapshot_and_restore(self, tmp_state):
        t = Task(id="t1", project_id="p1", title="Test")
        tmp_state.add_task(t)
        snap = tmp_state.snapshot("p1")
        assert snap["project_id"] == "p1"
        assert len(snap["tasks"]) == 1

        # Clear and restore
        tmp_state._tasks = {}
        tmp_state.restore("p1")
        assert tmp_state.get_task("t1") is not None

    def test_valid_transition(self, tmp_state):
        t = Task(id="t1", project_id="p1", title="Test", phase="created")
        tmp_state.add_task(t)
        tmp_state.transition("t1", "created", "cto")
        assert tmp_state.get_task("t1").phase == "cto"

    def test_invalid_transition(self, tmp_state):
        t = Task(id="t1", project_id="p1", title="Test", phase="created")
        tmp_state.add_task(t)
        with pytest.raises(ValueError):
            tmp_state.transition("t1", "created", "merge")

    def test_wrong_from_phase(self, tmp_state):
        t = Task(id="t1", project_id="p1", title="Test", phase="dev")
        tmp_state.add_task(t)
        with pytest.raises(ValueError):
            tmp_state.transition("t1", "created", "qa")

    def test_transition_to_done(self, tmp_state):
        t = Task(id="t1", project_id="p1", title="Test", phase="merge")
        tmp_state.add_task(t)
        tmp_state.transition("t1", "merge", "done")
        task = tmp_state.get_task("t1")
        assert task.phase == "done"
        assert task.status == "completed"
        assert task.completed_at is not None
