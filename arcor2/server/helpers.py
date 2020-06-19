from typing import Set

from arcor2.exceptions import Arcor2Exception


def unique_name(name: str, existing_names: Set[str]) -> None:

    if not name:
        raise Arcor2Exception("Name has to be set.")

    if name in existing_names:
        raise Arcor2Exception("Name already exists.")
