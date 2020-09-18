import functools
import io
import json
from typing import Any, Callable, Dict, List, Optional, Sequence, Type, TypeVar, Union, cast

import humps
import requests
from dataclasses_jsonschema import JsonSchemaMixin, ValidationError
from PIL import Image, UnidentifiedImageError  # type: ignore

from arcor2.exceptions import Arcor2Exception


class RestException(Arcor2Exception):
    pass


TIMEOUT = (1.0, 20.0)  # connect, read

HEADERS = {"accept": "application/json", "content-type": "application/json"}

T = TypeVar("T", bound=JsonSchemaMixin)
S = TypeVar("S", str, int, float, bool)

OptionalData = Optional[Union[JsonSchemaMixin, Sequence[JsonSchemaMixin], Sequence[S]]]
ParamsDict = Optional[Dict[str, Any]]
Files = Optional[Dict[str, bytes]]

SESSION = requests.session()

F = TypeVar("F", bound=Callable[..., Any])


def handle_exceptions(
    exception_type: Type[Arcor2Exception] = Arcor2Exception, message: Optional[str] = None
) -> Callable[[F], F]:
    def _handle_exceptions(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:

            try:
                return func(*args, **kwargs)
            except RestException as e:
                if message is not None:
                    raise exception_type(message, str(e)) from e
                else:
                    raise exception_type(e.message) from e

        return cast(F, wrapper)

    return _handle_exceptions


CK = TypeVar("CK", Dict[Any, Any], List[Any])


def handle_response(resp: requests.Response) -> None:
    try:
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:

        try:
            resp_body = json.loads(resp.content)
        except json.JSONDecodeError:
            raise RestException(resp.content.decode("utf-8"), str(e)) from e

        try:
            raise RestException(resp_body["message"], str(e)) from e
        except (KeyError, TypeError):  # TypeError is for case when resp_body is just string
            raise RestException(str(resp_body), str(e)) from e


def _send(
    url: str,
    op: Callable,
    data: OptionalData = None,
    params: ParamsDict = None,
    get_response=False,
    files: Files = None,
) -> Union[None, Dict, List]:

    if data and files:
        raise RestException("Can't send data and files at the same time.")

    if isinstance(data, JsonSchemaMixin):
        d = humps.camelize(data.to_dict())
    elif isinstance(data, list):
        d = []
        for dd in data:
            if isinstance(dd, JsonSchemaMixin):
                d.append(humps.camelize(dd.to_dict()))
            else:
                d.append(dd)
    elif data is not None:
        raise RestException("Unsupported type of data.")
    else:
        d = {}

    if params:
        params = humps.camelize(params)
    else:
        params = {}

    try:
        if files:
            resp = op(url, files=files, timeout=TIMEOUT, params=params)
        else:
            resp = op(url, data=json.dumps(d), timeout=TIMEOUT, headers=HEADERS, params=params)
    except requests.exceptions.RequestException as e:
        raise RestException("Catastrophic system error.", str(e)) from e

    handle_response(resp)

    if not get_response:
        return None

    try:
        return humps.decamelize(json.loads(resp.text))
    except (json.JSONDecodeError, TypeError) as e:
        raise RestException("Invalid JSON.", str(e)) from e


def post(url: str, data: JsonSchemaMixin, params: ParamsDict = None) -> None:
    _send(url, SESSION.post, data, params)


def put_returning_primitive(url: str, desired_type: Type[S], data: OptionalData = None, params: ParamsDict = None) -> S:

    try:
        return desired_type(_send(url, SESSION.put, data, params, get_response=True))  # type: ignore
    except ValueError as e:
        raise RestException(e) from e


def put(
    url: str, data: OptionalData = None, params: ParamsDict = None, data_cls: Type[T] = None, files: Files = None
) -> T:
    ret = _send(url, SESSION.put, data, params, get_response=data_cls is not None, files=files)  # type: ignore

    if not data_cls:
        return None  # type: ignore

    try:
        return data_cls.from_dict(ret)  # type: ignore
    except ValidationError as e:
        print(f'{data_cls.__name__}: validation error "{e}" while parsing "{data}".')
        raise RestException("Invalid data.", str(e)) from e


def put_returning_list(
    url: str, data: OptionalData = None, params: ParamsDict = None, data_cls: Type[T] = None
) -> List[T]:

    ret = _send(url, SESSION.put, data, params, get_response=data_cls is not None)  # type: ignore

    if not data_cls:
        return []  # type: ignore

    assert isinstance(ret, list)

    d = []
    for dd in ret:
        try:
            d.append(data_cls.from_dict(dd))  # type: ignore # TODO remove once pants/mypy works properly
        except ValidationError as e:
            print(f'{data_cls.__name__}: validation error "{e}" while parsing "{ret}".')
            raise RestException("Invalid data.", str(e)) from e

    return d


def delete(url: str) -> None:

    try:
        resp = SESSION.delete(url, timeout=TIMEOUT, headers=HEADERS)
    except requests.exceptions.RequestException as e:
        raise RestException("Catastrophic system error.", str(e)) from e

    handle_response(resp)


def get_data(url: str, body: Optional[JsonSchemaMixin] = None, params: ParamsDict = None) -> CK:

    data = _get(url, body, params)

    if not isinstance(data, (list, dict)):
        raise RestException("Invalid data, not list or dict.")

    return humps.decamelize(data)


def _get_response(url: str, body: Optional[JsonSchemaMixin] = None, params: ParamsDict = None) -> requests.Response:

    if body is None:
        body_dict = {}  # type: ignore
    else:
        body_dict = body.to_dict()

    if params:
        params = humps.camelize(params)
    else:
        params = {}

    try:
        resp = SESSION.get(url, timeout=TIMEOUT, data=body_dict, params=params, allow_redirects=True, headers=HEADERS)
    except requests.exceptions.RequestException as e:
        raise RestException("Catastrophic system error.", str(e)) from e

    handle_response(resp)

    return resp


def _get(url: str, body: Optional[JsonSchemaMixin] = None, params: ParamsDict = None) -> Any:

    resp = _get_response(url, body, params)

    try:
        return json.loads(resp.text)
    except (json.JSONDecodeError, TypeError) as e:
        raise RestException("Invalid JSON.", str(e)) from e


def get_image(url: str) -> Image.Image:

    # TODO check content type?
    try:
        return Image.open(io.BytesIO(_get_response(url).content))
    except (UnidentifiedImageError, TypeError) as e:
        raise RestException("Invalid image.", str(e)) from e


def get_primitive(
    url: str, desired_type: Type[S], body: Optional[JsonSchemaMixin] = None, params: ParamsDict = None
) -> S:

    value = _get(url, body, params)

    try:
        return desired_type(value)
    except ValueError as e:
        raise RestException("Invalid primitive.", str(e)) from e


def get_list(url: str, data_cls: Type[T], body: Optional[JsonSchemaMixin] = None, params: ParamsDict = None) -> List[T]:

    data = get_data(url, body, params)

    ret: List[T] = []

    for val in data:
        try:
            ret.append(data_cls.from_dict(val))  # type: ignore # TODO remove once pants/mypy works properly
        except ValidationError as e:
            print(f'{data_cls.__name__}: validation error "{e}" while parsing "{data}".')
            raise RestException("Invalid data.", str(e)) from e

    return ret


def get_list_primitive(
    url: str, desired_type: Type[S], body: Optional[JsonSchemaMixin] = None, params: ParamsDict = None
) -> List[S]:

    data = get_data(url, body, params)

    ret: List[S] = []

    for val in data:
        ret.append(desired_type(val))

    return ret


def get(url: str, data_cls: Type[T], body: Optional[JsonSchemaMixin] = None, params: ParamsDict = None) -> T:

    data = get_data(url, body, params)

    assert isinstance(data, dict)

    # TODO temporary workaround for bug in humps
    from arcor2.data.object_type import Box

    if data_cls is Box:
        data["size_x"] = data["sizex"]
        data["size_y"] = data["sizey"]
        data["size_z"] = data["sizez"]

    try:
        return data_cls.from_dict(data)  # type: ignore # TODO remove once pants/mypy works properly
    except ValidationError as e:
        raise RestException("Invalid data.", str(e)) from e


def download(url: str, path: str, body: Optional[JsonSchemaMixin] = None, params: ParamsDict = None) -> None:
    # TODO check content type

    r = _get_response(url, body, params)
    with open(path, "wb") as file:
        file.write(r.content)
