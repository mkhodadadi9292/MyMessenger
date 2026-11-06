import pytest

from file_service.domain.chunk_plan import ChunkPlan
from file_service.domain.exceptions import ValidationError


def test_total_chunks_rounds_up() -> None:
    assert ChunkPlan(10, 4).total_chunks == 3
    assert ChunkPlan(8, 4).total_chunks == 2
    assert ChunkPlan(1, 4).total_chunks == 1


def test_expected_length_is_chunk_size_except_last() -> None:
    plan = ChunkPlan(10, 4)
    assert [plan.expected_length(i) for i in range(3)] == [4, 4, 2]


def test_exact_multiple_has_full_last_chunk() -> None:
    assert ChunkPlan(8, 4).expected_length(1) == 4


@pytest.mark.parametrize("index", [-1, 3, 99])
def test_index_out_of_range_is_rejected(index: int) -> None:
    with pytest.raises(ValidationError):
        ChunkPlan(10, 4).expected_length(index)


def test_missing_lists_absent_indices_in_order() -> None:
    assert ChunkPlan(10, 4).missing({2, 0}) == [1]
    assert ChunkPlan(10, 4).missing({0, 1, 2}) == []


@pytest.mark.parametrize(("size", "chunk"), [(0, 4), (-1, 4), (10, 0)])
def test_non_positive_sizes_are_rejected(size: int, chunk: int) -> None:
    with pytest.raises(ValidationError):
        ChunkPlan(size, chunk)
