from arcor2.data.common import StrEnum
from arcor2.parameter_plugins.integer_enum import IntegerEnumPlugin


class StringEnumPlugin(IntegerEnumPlugin):

    @classmethod
    def type(cls):
        return StrEnum

    @classmethod
    def type_name(cls) -> str:
        return "string_enum"
