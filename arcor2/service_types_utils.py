from typing import Type, Iterator, Tuple
import inspect

from arcor2.services import Service
import arcor2.services
from arcor2.data.services import ServiceTypeMetaDict, ServiceTypeMeta


def meta_from_def(type_def: Type[Service], built_in: bool = False) -> ServiceTypeMeta:

    return ServiceTypeMeta(type_def.__name__,
                           type_def.description(),
                           set(type_def.get_configuration_ids()),
                           built_in)


def built_in_services() -> Iterator[Tuple[str, Type[Service]]]:
    """
    Yields class name and class definition tuple
    """

    for cls in inspect.getmembers(arcor2.services, inspect.isclass):
        # ignore abstract services
        if not issubclass(cls[1], Service) or inspect.isabstract(cls[1]) or cls[1] == Service:
            continue

        yield cls[0], cls[1]


def get_built_in_service(name: str) -> Type[Service]:

    for bname, cls in built_in_services():
        if name == bname:
            return cls

    raise KeyError


def built_in_services_meta() -> ServiceTypeMetaDict:

    service_types: ServiceTypeMetaDict = {}

    # built-in object types
    for type_name, type_def in built_in_services():
        service_types[type_name] = meta_from_def(type_def, built_in=True)

    return service_types
