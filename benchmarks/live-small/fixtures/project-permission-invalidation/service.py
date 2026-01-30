from permission_cache import PermissionCache
from project_cache import ProjectCache


class ProjectService:
    def __init__(self, projects: ProjectCache, permissions: PermissionCache) -> None:
        self.projects = projects
        self.permissions = permissions

    def delete_project(self, project_id: str) -> None:
        self.projects.delete(project_id)
