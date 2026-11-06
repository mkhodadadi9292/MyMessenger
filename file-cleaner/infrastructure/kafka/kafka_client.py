import asyncio
import json
from aiokafka import AIOKafkaProducer
from settings import settings


class KafkaClient:
    def __init__(self):
        self.bootstrap_servers = settings.kafka_url
        self._producer: AIOKafkaProducer | None = None

    async def get_producer(self) -> AIOKafkaProducer:
        if self._producer is not None:
            return self._producer

        backoff = 1
        max_backoff = 30

        while True:
            try:
                producer = AIOKafkaProducer(
                    bootstrap_servers=self.bootstrap_servers
                )
                await producer.start()
                self._producer = producer
                return producer

            except Exception as e:
                print(f"[Kafka] Producer connection failed: {e}. Retrying in {backoff} seconds...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)

    async def send(self, topic: str, event: dict):
        producer = await self.get_producer()
        value = json.dumps(event).encode("utf-8")
        await producer.send_and_wait(topic, value=value)
