class ProjectCache:
    def __init__(self) -> None:
        self._projects: dict[str, str] = {}

    def put(self, project_id: str, name: str) -> None:
        self._projects[project_id] = name

    def delete(self, project_id: str) -> None:
        self._projects.pop(project_id, None)

    def contains(self, project_id: str) -> bool:
        return project_id in self._projects
