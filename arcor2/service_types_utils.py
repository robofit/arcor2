from typing import Type

from arcor2.data.services import ServiceTypeMeta
from arcor2.services import Service


def meta_from_def(type_def: Type[Service]) -> ServiceTypeMeta:

    return ServiceTypeMeta(type_def.__name__,
                           type_def.description(),
                           type_def.get_configuration_ids())
