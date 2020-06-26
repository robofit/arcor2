import importlib
import inspect
import pkgutil
from typing import Iterator, Tuple, Type

from arcor2 import services
from arcor2.data.services import ServiceTypeMeta, ServiceTypeMetaDict
from arcor2.services.service import Service


def meta_from_def(type_def: Type[Service], built_in: bool = False) -> ServiceTypeMeta:

    return ServiceTypeMeta(type_def.__name__,
                           type_def.description(),
                           set(type_def.get_configuration_ids()),
                           built_in)


def built_in_services() -> Iterator[Tuple[str, Type[Service]]]:
    """
    Yields class name and class definition tuple
    """

    for module_info in pkgutil.iter_modules(services.__path__):  # type: ignore  # mypy issue #1422

        module = importlib.import_module(f"arcor2.services.{module_info.name}")

        for cls_name, cls in inspect.getmembers(module, inspect.isclass):

            # ignore abstract services
            if not issubclass(cls, Service) or inspect.isabstract(cls) or cls == Service:
                continue

            yield cls_name, cls


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
