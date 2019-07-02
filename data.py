#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import List, Callable, Any
from dataclasses import dataclass, field
from dataclasses_json import DataClassJsonMixin  # latest release (with to_dict()) not yet available through pip, install it from git!
from json import JSONEncoder

AnyFunction = Callable[[Any], Any]


class DataClassEncoder(JSONEncoder):

    def default(self, o):

        if isinstance(o, DataClassJsonMixin):
            return o.to_dict()

        return o.__dict__

@dataclass
class Pose(DataClassJsonMixin):

    position: List[float] = field(default_factory=lambda: [0, 0, 0])
    orientation: List[float] = field(default_factory=lambda: [0, 0, 0, 1])

    def __post_init__(self):

        assert len(self.position) == 3
        assert len(self.orientation) == 4


@dataclass
class ActionMetadata:

    api_name: str
    free: bool = False
    blocking: bool = False


@dataclass
class ActionPoint(DataClassJsonMixin):

    name: str
    pose: Pose = field(default_factory=Pose)
