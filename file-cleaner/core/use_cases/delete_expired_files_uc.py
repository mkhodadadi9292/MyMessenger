from core.interfaces.cleaner_repository import ICleanerRepository
from core.interfaces.cleanup_api import ICleanupAPI
from core.interfaces.kafka_publisher import IKafkaPublisher

class DeleteExpiredFilesUC:
    def __init__(self, repo: ICleanerRepository, api: ICleanupAPI, publisher: IKafkaPublisher):
        self.repo = repo
        self.api = api
        self.publisher = publisher

    async def execute(self):
        files = await self.repo.get_expired_files()

        for file in files:
            await self.api.delete(file.file_id)
            await self.publisher.publish_delete(file.lookup_key)
