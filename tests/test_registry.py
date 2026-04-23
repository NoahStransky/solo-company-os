"""Tests for projectos/core/registry.py."""
import pytest
from pathlib import Path

from projectos.core.registry import ProjectRegistry
from projectos.core.models import Project


@pytest.fixture
def tmp_registry(tmp_path):
    db = tmp_path / "projects.json"
    return ProjectRegistry(str(db))


class TestProjectRegistry:
    def test_create_project(self, tmp_registry):
        p = Project(id="test-1", name="Test", repo_url="https://example.com", local_path="/tmp/test")
        pid = tmp_registry.create(p)
        assert pid == "test-1"
        assert tmp_registry.exists("test-1")

    def test_create_duplicate_raises(self, tmp_registry):
        p = Project(id="dup", name="Dup", repo_url="", local_path="")
        tmp_registry.create(p)
        with pytest.raises(ValueError):
            tmp_registry.create(p)

    def test_get_existing(self, tmp_registry):
        p = Project(id="get-me", name="Get", repo_url="", local_path="")
        tmp_registry.create(p)
        found = tmp_registry.get("get-me")
        assert found is not None
        assert found.name == "Get"

    def test_get_missing(self, tmp_registry):
        assert tmp_registry.get("missing") is None

    def test_list_all(self, tmp_registry):
        tmp_registry.create(Project(id="a", name="A", repo_url="", local_path=""))
        tmp_registry.create(Project(id="b", name="B", repo_url="", local_path=""))
        assert len(tmp_registry.list()) == 2

    def test_list_by_status(self, tmp_registry):
        tmp_registry.create(Project(id="act", name="Active", repo_url="", local_path="", status="active"))
        tmp_registry.create(Project(id="pau", name="Paused", repo_url="", local_path="", status="paused"))
        assert len(tmp_registry.list(status="active")) == 1
        assert tmp_registry.list(status="active")[0].id == "act"

    def test_update(self, tmp_registry):
        tmp_registry.create(Project(id="up", name="Up", repo_url="", local_path=""))
        tmp_registry.update("up", status="paused")
        assert tmp_registry.get("up").status == "paused"

    def test_delete(self, tmp_registry):
        tmp_registry.create(Project(id="del", name="Del", repo_url="", local_path=""))
        tmp_registry.delete("del")
        assert not tmp_registry.exists("del")

    def test_persistence(self, tmp_path):
        db = tmp_path / "persist.json"
        reg = ProjectRegistry(str(db))
        reg.create(Project(id="persist", name="Persist", repo_url="", local_path=""))

        reg2 = ProjectRegistry(str(db))
        assert reg2.exists("persist")
        assert reg2.get("persist").name == "Persist"
