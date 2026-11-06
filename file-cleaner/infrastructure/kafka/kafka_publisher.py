from core.interfaces.kafka_publisher import IKafkaPublisher
from infrastructure.kafka.kafka_client import KafkaClient
from infrastructure.kafka.topics import FILES_CLEANER_EVENTS


class FileCleanerPublisherImpl(IKafkaPublisher):
    def __init__(self, client: KafkaClient):
        self.client = client

    async def publish_delete(self, lookup_key: str) -> None:
        event = {
            "type": "file.cleaner.deleted",
            "data": {
                "lookup_key": lookup_key,
            },
        }

        await self.client.send(FILES_CLEANER_EVENTS, event)
