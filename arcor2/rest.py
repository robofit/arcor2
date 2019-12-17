import json
import requests
from typing import Type, TypeVar, Dict, Callable, List, Union, Any, Optional, Sequence

from dataclasses_jsonschema import ValidationError, JsonSchemaMixin

from arcor2.exceptions import Arcor2Exception
from arcor2.helpers import camel_case_to_snake_case, snake_case_to_camel_case


class RestException(Arcor2Exception):
    pass


TIMEOUT = (1.0, 20.0)  # connect, read

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


def _send(url: str, op: Callable, data: Optional[Union[JsonSchemaMixin, List[JsonSchemaMixin]]] = None,
          params: Optional[Dict] = None, get_response=False) -> Optional[Dict]:

    if data:
        if isinstance(data, list):
            d = []
            for dd in data:
                d.append(convert_keys(dd.to_dict(), snake_case_to_camel_case))
        else:
            d = convert_keys(data.to_dict(), snake_case_to_camel_case)  # type: ignore
    else:
        d = {}  # type: ignore

    if params:
        params = convert_keys(params, snake_case_to_camel_case)  # type: ignore
    else:
        params = {}

    try:
        resp = op(url, data=json.dumps(d), timeout=TIMEOUT, headers={'Content-Type': 'application/json'},
                  params=params)
    except requests.exceptions.RequestException as e:
        print(e)
        raise RestException(f"Catastrophic error: {e}")

    handle_response(resp)

    if not get_response:
        return None

    print(resp.text)

    try:
        return json.loads(resp.text)
    except (json.JSONDecodeError, TypeError) as e:
        print(e)
        raise RestException("Invalid JSON.")


def post(url: str, data: JsonSchemaMixin, params: Optional[Dict] = None):
    _send(url, requests.post, data, params)


def put(url: str, data: Optional[Union[JsonSchemaMixin, Sequence[JsonSchemaMixin]]] = None,
        params: Optional[Dict] = None, data_cls: Type[T] = None) -> T:
    ret = _send(url, requests.put, data, params, get_response=data_cls is not None)  # type: ignore

    if not data_cls:
        return None  # type: ignore

    try:
        return data_cls.from_dict(ret)  # type: ignore
    except ValidationError as e:
        print(f'{data_cls.__name__}: validation error "{e}" while parsing "{data}".')
        raise RestException("Invalid data.")


def delete(url: str):

    try:
        resp = requests.delete(url, timeout=TIMEOUT)
    except requests.exceptions.RequestException as e:
        print(e)
        raise RestException(f"Catastrophic error: {e}")

    handle_response(resp)


def get_data(url: str, body: Optional[JsonSchemaMixin] = None, params: Optional[Dict] = None) -> Union[Dict, List]:

    data = _get(url, body, params)

    if not isinstance(data, (list, dict)):
        raise RestException("Invalid data.")

    return convert_keys(data, camel_case_to_snake_case)


def _get(url: str, body: Optional[JsonSchemaMixin] = None, params: Optional[Dict] = None) -> Any:

    if body is None:
        body_dict = {}  # type: ignore
    else:
        body_dict = body.to_dict()

    if params:
        params = convert_keys(params, snake_case_to_camel_case)  # type: ignore
    else:
        params = {}

    try:
        resp = requests.get(url, timeout=TIMEOUT, data=body_dict, params=params)
    except requests.exceptions.RequestException as e:
        print(e)
        raise RestException(f"Catastrophic error: {e}")

    handle_response(resp)

    try:
        return json.loads(resp.text)
    except (json.JSONDecodeError, TypeError) as e:
        print(e)
        raise RestException("Invalid JSON.")


def get_float(url: str, body: Optional[JsonSchemaMixin] = None, params: Optional[Dict] = None) -> float:

    value = _get(url, body, params)

    try:
        return float(value)
    except ValueError as e:
        raise RestException(e)


def get_bool(url: str, body: Optional[JsonSchemaMixin] = None, params: Optional[Dict] = None) -> bool:

    value = _get(url, body, params)

    try:
        return bool(value)
    except ValueError as e:
        raise RestException(e)


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


def get(url: str, data_cls: Type[T], body: Optional[JsonSchemaMixin] = None) -> T:

    data = get_data(url, body)

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

    handle_response(r)

    with open(path, 'wb') as file:
        file.write(r.content)
