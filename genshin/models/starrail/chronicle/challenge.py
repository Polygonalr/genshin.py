"""Starrail chronicle challenge."""
from typing import List

from genshin.models.model import Aliased, APIModel
from genshin.models.starrail.character import FloorCharacter

from .base import PartialTime

__all__ = ["FloorNode", "StarRailChallenge", "StarRailFloor", "StarRailChallengeStory"]


class FloorNode(APIModel):
    """Node for a floor."""

    challenge_time: PartialTime
    avatars: List[FloorCharacter]


class StarRailFloor(APIModel):
    """Floor in a challenge."""

    name: str
    round_num: int
    star_num: int
    node_1: FloorNode
    node_2: FloorNode
    is_chaos: bool


class StarRailChallenge(APIModel):
    """Challenge in a season."""

    season: int = Aliased("schedule_id")
    begin_time: PartialTime
    end_time: PartialTime

    total_stars: int = Aliased("star_num")
    max_floor: str
    total_battles: int = Aliased("battle_num")
    has_data: bool

    floors: List[StarRailFloor] = Aliased("all_floor_detail")


class StoryBuff(APIModel):
    """Buff for a Pure Fiction floor."""

    name: str = Aliased("name_mi18n")
    description: str = Aliased("desc_mi18n")
    icon: str


class StoryFloorNode(APIModel):
    """Node for a Pure Fiction floor."""

    challenge_time: PartialTime
    avatars: List[FloorCharacter]
    buff: StoryBuff
    score: int


class StarRailFloorStory(APIModel):
    """Floor in a Pure Fiction challenge."""

    name: str
    round_num: int
    star_num: int
    node_1: StoryFloorNode
    node_2: StoryFloorNode
    is_fast: bool


class StarRailChallengeStory(APIModel):
    """Pure Fiction challenge in a season."""

    season: int = Aliased("schedule_id")
    begin_time: PartialTime
    end_time: PartialTime

    total_stars: int = Aliased("star_num")
    max_floor: str
    total_battles: int = Aliased("battle_num")
    has_data: bool

    floors: List[StarRailFloorStory] = Aliased("all_floor_detail")
