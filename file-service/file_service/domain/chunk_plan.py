from dataclasses import dataclass

from file_service.domain.exceptions import ValidationError


@dataclass(frozen=True)
class ChunkPlan:
    size_bytes: int
    chunk_size: int

    def __post_init__(self) -> None:
        if self.size_bytes <= 0:
            raise ValidationError("size_bytes must be positive")
        if self.chunk_size <= 0:
            raise ValidationError("chunk_size must be positive")

    @property
    def total_chunks(self) -> int:
        return -(-self.size_bytes // self.chunk_size)

    def expected_length(self, index: int) -> int:
        if index < 0 or index >= self.total_chunks:
            raise ValidationError(f"chunk index must be between 0 and {self.total_chunks - 1}")
        if index == self.total_chunks - 1:
            return self.size_bytes - self.chunk_size * (self.total_chunks - 1)
        return self.chunk_size

    def missing(self, received: set[int]) -> list[int]:
        return [index for index in range(self.total_chunks) if index not in received]
