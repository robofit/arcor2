import json
import requests

from typing import Type, TypeVar, Dict, Callable, List, Union, Any, Optional

from dataclasses_jsonschema import ValidationError, JsonSchemaMixin


from arcor2.exceptions import Arcor2Exception
from arcor2.helpers import camel_case_to_snake_case, snake_case_to_camel_case


class RestException(Arcor2Exception):
    pass


TIMEOUT = (1.0, 1.0)  # connect, read

T = TypeVar('T', bound=JsonSchemaMixin)


def convert_keys(d: Union[Dict, List], func: Callable[[str], str]) -> Union[Dict, List]:

    if isinstance(d, dict):
        new_dict = {}
        for k, v in d.items():
            new_dict[func(k)] = convert_keys(v, func)
        return new_dict
    elif isinstance(d, list):
        new_list: List[Any] = []
        for dd in d:
            new_list.append(convert_keys(dd, func))
        return new_list

    return d


def handle_response(resp: requests.Response) -> None:
    try:
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(e)

        try:
            resp_body = json.loads(resp.content)
        except json.JSONDecodeError:
            resp_body = resp.content

        raise RestException(f"Status code: {resp.status_code}, "
                            f"body: {resp_body}.")


def _send(url: str, op: Callable, data: Optional[JsonSchemaMixin] = None) -> None:

    if data:
        d = convert_keys(data.to_dict(), snake_case_to_camel_case)
    else:
        d = {}

    try:
        resp = op(url, data=json.dumps(d), timeout=TIMEOUT, headers={'Content-Type': 'application/json'})
    except requests.exceptions.RequestException as e:
        print(e)
        raise RestException(f"Catastrophic error: {e}")

    handle_response(resp)


def post(url: str, data: JsonSchemaMixin):
    _send(url, requests.post, data)


def put(url: str, data: Optional[JsonSchemaMixin] = None):
    _send(url, requests.put, data)


def get_data(url: str) -> Union[Dict, List]:
    try:
        resp = requests.get(url, timeout=TIMEOUT)
    except requests.exceptions.RequestException as e:
        print(e)
        raise RestException(f"Catastrophic error: {e}")

    handle_response(resp)

    try:
        data = json.loads(resp.text)
    except (json.JSONDecodeError, TypeError) as e:
        print(e)
        raise RestException("Invalid JSON.")

    return convert_keys(data, camel_case_to_snake_case)


def get_list(url: str, data_cls: Type[T]) -> List[T]:
    data = get_data(url)

    ret: List[T] = []

    for val in data:
        try:
            ret.append(data_cls.from_dict(val))
        except ValidationError as e:
            print(f'{data_cls.__name__}: validation error "{e}" while parsing "{data}".')
            raise RestException("Invalid data.")

    return ret


def get(url: str, data_cls: Type[T]) -> T:
    data = get_data(url)

    assert isinstance(data, dict)

    try:
        return data_cls.from_dict(data)
    except ValidationError as e:
        print(f'{data_cls.__name__}: validation error "{e}" while parsing "{data}".')
        raise RestException("Invalid data.")


def download(url: str, path: str) -> None:
    # TODO check content type

    try:
        r = requests.get(url, allow_redirects=True)
    except requests.exceptions.RequestException as e:
        print(e)
        raise RestException("Download of file failed.")

    with open(path, 'wb') as file:
        file.write(r.content)
