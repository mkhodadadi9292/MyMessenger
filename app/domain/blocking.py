from dataclasses import dataclass


@dataclass(frozen=True)
class BlockRelation:
    actor_blocks_target: bool
    target_blocks_actor: bool


def can_interact(relation: BlockRelation) -> bool:
    return not (relation.actor_blocks_target or relation.target_blocks_actor)
