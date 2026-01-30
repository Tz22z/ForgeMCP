from permission_cache import PermissionCache
from project_cache import ProjectCache
from service import ProjectService


def test_delete_invalidates_only_target_project_permissions() -> None:
    projects = ProjectCache()
    projects.put("p1", "First")
    projects.put("p2", "Second")
    permissions = PermissionCache()
    permissions.put("p1", "u1", frozenset({"read"}))
    permissions.put("p1", "u2", frozenset({"write"}))
    permissions.put("p2", "u1", frozenset({"admin"}))

    ProjectService(projects, permissions).delete_project("p1")

    assert not projects.contains("p1")
    assert permissions.get("p1", "u1") is None
    assert permissions.get("p1", "u2") is None
    assert permissions.get("p2", "u1") == frozenset({"admin"})
