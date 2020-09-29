from arcor2 import rest
from arcor2.data.common import ActionMetadata

from .kinali_abstract_object import KinaliAbstractObject


class Barcode(KinaliAbstractObject):
    """REST interface to the barcode service (0.3.0)."""

    _ABSTRACT = False

    def scan(self) -> str:
        """Gets scan from active scanner.

        :return:
        """

        return rest.get_primitive(f"{self.settings.url}/scanner/scan", str)

    scan.__action__ = ActionMetadata(blocking=True)  # type: ignore
