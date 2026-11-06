from datetime import datetime, timedelta, timezone
from core.interfaces.cleaner_repository import ICleanerRepository
from core.interfaces.cleanup_api import ICleanupAPI
from core.interfaces.kafka_publisher import IKafkaPublisher

class DeleteUncommittedFilesUC:
    def __init__(self, repo: ICleanerRepository, api: ICleanupAPI, publisher: IKafkaPublisher, threshold_minutes: int = 60):
        self.repo = repo
        self.api = api
        self.publisher = publisher
        self.threshold_minutes = threshold_minutes

    async def execute(self):
        files = await self.repo.get_uncommitted_files(self.threshold_minutes)
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=self.threshold_minutes)

        for file in files:
            if file.last_seen_at < cutoff:
                await self.api.delete(file.file_id)
                await self.publisher.publish_delete(file.lookup_key)
