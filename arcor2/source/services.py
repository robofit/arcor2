import arcor2.helpers as hlp
from arcor2.source import SourceException
from arcor2.object_types_utils import object_actions
from arcor2.services import Service
from arcor2.parameter_plugins import TYPE_TO_PLUGIN


def check_service_type(service_type_source: str, type_name: str) -> None:
    """
    Checks whether the service type source is a valid one.
    :param service_type_source: Source code.
    :param type_name: Class name.
    :return:
    """
    try:
        type_def = hlp.type_def_from_source(service_type_source, type_name, Service)
    except hlp.TypeDefException as e:
        raise SourceException(e)

    # meta_from_def(type_def)  # calls API which is probably undesirable for check
    object_actions(TYPE_TO_PLUGIN, type_def, service_type_source)
