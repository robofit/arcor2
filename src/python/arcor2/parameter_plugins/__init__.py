from typing import Dict, Type

from arcor2.exceptions import Arcor2Exception
from arcor2.object_types.abstract import Generic

TypesDict = Dict[str, Type[Generic]]


class ParameterPluginException(Arcor2Exception):
    pass
