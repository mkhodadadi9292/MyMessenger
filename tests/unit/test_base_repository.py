from app.domain.repositories.base import AbstractRepository


class FakeRepository(AbstractRepository[dict, int]):
    def __init__(self) -> None:
        self._items: dict[int, dict] = {}

    async def get(self, entity_id: int) -> dict | None:
        return self._items.get(entity_id)

    async def add(self, entity: dict) -> dict:
        self._items[entity["id"]] = entity
        return entity

    async def delete(self, entity: dict) -> None:
        self._items.pop(entity["id"], None)


def test_repository_is_abstract() -> None:
    assert AbstractRepository.__abstractmethods__ == {"get", "add", "delete"}


async def test_fake_repository_satisfies_contract() -> None:
    repo = FakeRepository()
    assert await repo.get(1) is None
    await repo.add({"id": 1, "name": "a"})
    assert (await repo.get(1))["name"] == "a"
    await repo.delete({"id": 1})
    assert await repo.get(1) is None
