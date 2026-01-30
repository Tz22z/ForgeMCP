class PermissionCache:
    def __init__(self) -> None:
        self._permissions: dict[tuple[str, str], frozenset[str]] = {}

    def put(self, project_id: str, user_id: str, values: frozenset[str]) -> None:
        self._permissions[(project_id, user_id)] = values

    def get(self, project_id: str, user_id: str) -> frozenset[str] | None:
        return self._permissions.get((project_id, user_id))

    def invalidate_project(self, project_id: str) -> None:
        self._permissions = {
            key: value for key, value in self._permissions.items() if key[0] != project_id
        }
