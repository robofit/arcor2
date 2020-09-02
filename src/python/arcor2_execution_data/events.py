from dataclasses import dataclass

from arcor2.data.events import Event
from arcor2_execution_data.common import PackageSummary


@dataclass
class PackageChanged(Event):

    data: PackageSummary
