"""Tests for projectos/core/scheduler.py."""
import pytest
from projectos.core.scheduler import AgentScheduler
from projectos.core.registry import ProjectRegistry
from projectos.core.models import Project, Task


@pytest.fixture
def tmp_scheduler(tmp_path):
    db = tmp_path / "projects.json"
    reg = ProjectRegistry(str(db))
    return AgentScheduler(reg)


class TestAgentScheduler:
    def test_assign_and_release(self, tmp_scheduler):
        reg = tmp_scheduler.registry
        reg.create(Project(id="p1", name="P1", repo_url="", local_path=""))
        t = Task(id="t1", project_id="p1", title="Task 1")

        aid = tmp_scheduler.assign(t, "dev")
        assert aid is not None
        assert aid.startswith("dev-")
        assert t.status == "in_progress"

        tmp_scheduler.release(aid)
        agent = tmp_scheduler.agents[aid]
        assert agent.status == "idle"
        assert agent.current_project is None

    def test_per_project_limit(self, tmp_scheduler):
        reg = tmp_scheduler.registry
        reg.create(Project(id="p1", name="P1", repo_url="", local_path=""))
        t1 = Task(id="t1", project_id="p1", title="Task 1")
        t2 = Task(id="t2", project_id="p1", title="Task 2")

        tmp_scheduler.assign(t1, "dev")
        aid2 = tmp_scheduler.assign(t2, "dev")
        # Should be queued (None returned)
        assert aid2 is None
        assert t2.status == "pending"

    def test_global_dev_limit(self, tmp_scheduler):
        reg = tmp_scheduler.registry
        for i in range(4):
            reg.create(Project(id=f"p{i}", name=f"P{i}", repo_url="", local_path=""))

        for i in range(4):
            t = Task(id=f"t{i}", project_id=f"p{i}", title=f"Task {i}")
            tmp_scheduler.assign(t, "dev")

        # Only 3 dev agents should be busy globally
        busy = tmp_scheduler.get_busy_agents("dev")
        assert len(busy) == 3

    def test_queue_priority(self, tmp_scheduler):
        reg = tmp_scheduler.registry
        reg.create(Project(id="p1", name="P1", repo_url="", local_path=""))
        # Fill up the single dev slot
        t1 = Task(id="t1", project_id="p1", title="First", priority=3)
        tmp_scheduler.assign(t1, "dev")

        t2 = Task(id="t2", project_id="p1", title="Low", priority=5)
        t3 = Task(id="t3", project_id="p1", title="High", priority=1)
        tmp_scheduler.queue(t2)
        tmp_scheduler.queue(t3)

        queue = tmp_scheduler.get_queue("p1")
        assert queue[0].id == "t3"  # High priority first
        assert queue[1].id == "t2"

    def test_can_start(self, tmp_scheduler):
        reg = tmp_scheduler.registry
        reg.create(Project(id="p1", name="P1", repo_url="", local_path=""))
        assert tmp_scheduler.can_start("p1", "dev") is True
        t = Task(id="t1", project_id="p1", title="Task")
        tmp_scheduler.assign(t, "dev")
        assert tmp_scheduler.can_start("p1", "dev") is False
