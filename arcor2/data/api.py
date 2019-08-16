# -*- coding: utf-8 -*-

from typing import Dict, List, Any

from dataclasses import dataclass, field
from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.common import ObjectAction, ObjectTypeMeta


@dataclass
class request(JsonSchemaMixin):

    request: str
    args: Dict


@dataclass
class response(JsonSchemaMixin):

    response: str
    result: bool = True
    messages: List[str] = field(default_factory=list)
    data: List[Any] = field(default_factory=list)


@dataclass
class EmptyArgs(JsonSchemaMixin):
    pass


@dataclass
class getObjectTypesDataItem(JsonSchemaMixin):

    type: str
    description: str
    built_in: bool
    base: str


@dataclass
class getObjectActionsArgs(JsonSchemaMixin):

    type: str


MAPPING = {"getObjectTypes": (EmptyArgs, ObjectTypeMeta),
           "getObjectActions": (getObjectActionsArgs, ObjectAction)}
