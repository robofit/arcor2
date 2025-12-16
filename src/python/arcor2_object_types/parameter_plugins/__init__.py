from arcor2.exceptions import Arcor2Exception
from arcor2_object_types.abstract import Generic

TypesDict = dict[str, type[Generic]]


class ParameterPluginException(Arcor2Exception):
    pass
