import pytest

from app.domain.blocking import BlockRelation, can_interact


@pytest.mark.parametrize(
    ("a_blocks_b", "b_blocks_a", "expected"),
    [
        (False, False, True),
        (True, False, False),
        (False, True, False),
        (True, True, False),
    ],
)
def test_can_interact_matrix(a_blocks_b: bool, b_blocks_a: bool, expected: bool) -> None:
    relation = BlockRelation(actor_blocks_target=a_blocks_b, target_blocks_actor=b_blocks_a)
    assert can_interact(relation) is expected
