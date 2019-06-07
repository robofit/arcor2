#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import List, Callable, Set, Any
from dataclasses import dataclass, field

AnyFunction = Callable[[Any], Any]


@dataclass
class Pose:

    position: List[float] = field(default_factory=lambda: [0, 0, 0])
    orientation: List[float] = field(default_factory=lambda: [0, 0, 0, 1])

    def __post_init__(self):

        assert len(self.position) == 3
        assert len(self.orientation) == 4


@dataclass
class Instructions:

    free: Set[AnyFunction] = field(default_factory=set)
    bound: Set[AnyFunction] = field(default_factory=set)
    blocking: Set[AnyFunction] = field(default_factory=set)

    @property
    def all(self) -> Set[Callable]:

        return self.free | self.bound | self.blocking


@dataclass
class ActionPoint:

    name: str
    pose: Pose = field(default_factory=Pose)