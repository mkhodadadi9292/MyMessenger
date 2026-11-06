from abc import ABC, abstractmethod

class IKafkaPublisher(ABC):
    @abstractmethod
    async def publish_delete(self, lookup_key: str) -> None:
        pass
