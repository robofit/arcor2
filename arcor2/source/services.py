import arcor2.helpers as hlp
from arcor2.source import SourceException
from arcor2.object_types_utils import object_actions
from arcor2.services import Service


def check_service_type(service_type_source: str, type_name: str) -> None:
    """
    Checks whether the service type source is a valid one.
    :param object_type_source:
    :return:
    """
    try:
        type_def = hlp.type_def_from_source(service_type_source, type_name, Service)
    except hlp.TypeDefException as e:
        raise SourceException(e)

    # meta_from_def(type_def)  # calls API which is probably undesirable for check
    object_actions(type_def)
