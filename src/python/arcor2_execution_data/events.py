from dataclasses import dataclass, field
from typing import Optional

from arcor2.data.events import Event, wo_suffix
from arcor2_execution_data.common import PackageSummary


@dataclass
class PackageChanged(Event):

    data: Optional[PackageSummary] = None
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821
