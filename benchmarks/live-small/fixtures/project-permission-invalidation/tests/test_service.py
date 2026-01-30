from permission_cache import PermissionCache
from project_cache import ProjectCache
from service import ProjectService


def test_delete_removes_project() -> None:
    projects = ProjectCache()
    projects.put("p1", "First")
    service = ProjectService(projects, PermissionCache())

    service.delete_project("p1")

    assert not projects.contains("p1")
