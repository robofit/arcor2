from typing import Iterable, Union

ObjIds = Union[Iterable[str], str]


def obj_ids_to_list(val: ObjIds) -> list[str]:

    if isinstance(val, str):
        return [val]
    elif isinstance(val, list):
        return val
    else:
        return list(val)
