from typing import List

from arcor2 import rest
from arcor2.data.common import ActionMetadata
from arcor2_kinali.object_types.kinali_abstract_object import KinaliAbstractObject


class Barcode(KinaliAbstractObject):
    """REST interface to the barcode service."""

    _ABSTRACT = False

    def active_scanners(self) -> List[str]:
        """Gets scanners ids.

        :return:
        """
        return rest.get_list_primitive(f"{self.settings.url}/scanners", str)

    def scan(self, scanner_id: str) -> str:
        """Gets scan.

        :param scanner_id:
        :return:
        """

        return rest.get_primitive(f"{self.settings.url}/scanners/{scanner_id}/scan", str)

    active_scanners.__action__ = ActionMetadata(blocking=True)  # type: ignore
    scan.__action__ = ActionMetadata(blocking=True)  # type: ignore
