import logging
from enum import Enum
from functools import partial
from io import BytesIO
from typing import Any, Dict, List, NamedTuple, Optional, Sequence, Type, TypeVar, Union, overload

import humps
import requests
from dataclasses_jsonschema import JsonSchemaMixin, ValidationError
from PIL import Image, UnidentifiedImageError

from arcor2 import env, json
from arcor2.exceptions import Arcor2Exception
from arcor2.logging import get_logger

# typing-related definitions
DataClass = TypeVar("DataClass", bound=JsonSchemaMixin)
Primitive = TypeVar("Primitive", str, int, float, bool)
ReturnValue = Union[None, Primitive, DataClass, BytesIO]
ReturnType = Union[None, Type[Primitive], Type[DataClass], Type[BytesIO]]

OptBody = Optional[Union[JsonSchemaMixin, Sequence[JsonSchemaMixin], Sequence[Primitive]]]
OptParams = Optional[Dict[str, Primitive]]
OptFiles = Optional[Dict[str, Union[bytes, str]]]


class RestException(Arcor2Exception):
    """Exception raised by functions in the module."""

    pass


class RestHttpException(RestException):
    """Exception with associated HTTP status (error) code."""

    def __init__(self, *args, error_code: int):
        super().__init__(*args)
        self.error_code = error_code


class Method(Enum):
    """Enumeration of supported HTTP methods."""

    GET = partial(requests.get)
    POST = partial(requests.post)
    PUT = partial(requests.put)
    DELETE = partial(requests.delete)
    PATCH = partial(requests.patch)


class Timeout(NamedTuple):
    """The connect timeout is the number of seconds Requests will wait for your
    client to establish a connection to a remote machine (corresponding to the
    connect()) call on the socket. It’s a good practice to set connect timeouts
    to slightly larger than a multiple of 3, which is the default TCP packet
    retransmission window.

    Once your client has connected to the server and sent the HTTP request,
    the read timeout is the number of seconds the client will wait for the server
    to send a response. (Specifically, it’s the number of seconds that the client
    will wait between bytes sent from the server. In 99.9% of cases, this is
    the time before the server sends the first byte).

    Source: https://requests.readthedocs.io/en/master/user/advanced/#timeouts
    """

    connect: float = 3.05
    read: float = 20.0


OptTimeout = Optional[Timeout]


# module-level variables
debug = env.get_bool("ARCOR2_REST_DEBUG", False)
headers = {"accept": "application/json", "content-type": "application/json"}
session = requests.session()
logger = get_logger(__name__, logging.DEBUG if debug else logging.INFO)


def dataclass_from_json(resp_json: Dict[str, Any], return_type: Type[DataClass]) -> DataClass:

    try:
        return return_type.from_dict(resp_json)
    except ValidationError as e:
        logger.debug(f'{return_type.__name__}: validation error "{e}" while parsing "{resp_json}".')
        raise RestException("Invalid data.", str(e)) from e


def primitive_from_json(resp_json: Primitive, return_type: Type[Primitive]) -> Primitive:

    try:
        return return_type(resp_json)
    except ValueError as e:
        logger.debug(f'{return_type.__name__}: error  "{e}" while parsing "{resp_json}".')
        raise RestException(e) from e


# overload for no return
@overload
def call(
    method: Method,
    url: str,
    *,
    body: OptBody = None,
    params: OptParams = None,
    files: OptFiles = None,
    timeout: OptTimeout = None,
) -> None:
    ...


# single value-returning overloads
@overload
def call(
    method: Method,
    url: str,
    *,
    return_type: Type[Primitive],
    body: OptBody = None,
    params: OptParams = None,
    files: OptFiles = None,
    timeout: OptTimeout = None,
) -> Primitive:
    ...


@overload
def call(
    method: Method,
    url: str,
    *,
    return_type: Type[DataClass],
    body: OptBody = None,
    params: OptParams = None,
    files: OptFiles = None,
    timeout: OptTimeout = None,
) -> DataClass:
    ...


@overload
def call(
    method: Method,
    url: str,
    *,
    return_type: Type[BytesIO],
    body: OptBody = None,
    params: OptParams = None,
    files: OptFiles = None,
    timeout: OptTimeout = None,
) -> BytesIO:
    ...


# list-returning overloads
@overload
def call(
    method: Method,
    url: str,
    *,
    list_return_type: Type[Primitive],
    body: OptBody = None,
    params: OptParams = None,
    files: OptFiles = None,
    timeout: OptTimeout = None,
) -> List[Primitive]:
    ...


@overload
def call(
    method: Method,
    url: str,
    *,
    list_return_type: Type[DataClass],
    body: OptBody = None,
    params: OptParams = None,
    files: OptFiles = None,
    timeout: OptTimeout = None,
) -> List[DataClass]:
    ...


@overload
def call(
    method: Method,
    url: str,
    *,
    list_return_type: Type[BytesIO],
    body: OptBody = None,
    params: OptParams = None,
    files: OptFiles = None,
    timeout: OptTimeout = None,
) -> List[BytesIO]:
    ...


def call(
    method: Method,
    url: str,
    *,
    return_type: ReturnType = None,
    list_return_type: ReturnType = None,
    body: OptBody = None,
    params: OptParams = None,
    files: OptFiles = None,
    timeout: OptTimeout = None,
) -> ReturnValue:
    """Universal function for calling REST APIs.

    :param method: HTTP method.
    :param url: Resource address.
    :param return_type: If set, function will try to return one value of a given type.
    :param list_return_type: If set, function will try to return list of a given type.
    :param body: Data to be send in the request body.
    :param params: Path parameters.
    :param files: Instead of body, it is possible to send files.
    :param timeout: Specific timeout for a call.
    :return: Return value/type is given by return_type/list_return_type. If both are None, nothing will be returned.
    """
    logger.debug(f"{method} {url}, body: {body}, params: {params}, files: {files is not None}, timeout: {timeout}")

    if body and files:
        raise RestException("Can't send data and files at the same time.")

    if return_type and list_return_type:
        raise RestException("Only one argument from 'return_type' and 'list_return_type' can be used.")

    if return_type is None:
        return_type = list_return_type

    # prepare data into dict
    if isinstance(body, JsonSchemaMixin):
        d = humps.camelize(body.to_dict())
    elif isinstance(body, list):
        d = []
        for dd in body:
            if isinstance(dd, JsonSchemaMixin):
                d.append(humps.camelize(dd.to_dict()))
            else:
                d.append(dd)
    elif body is not None:
        raise RestException("Unsupported type of data.")
    else:
        d = {}

    if params:
        params = humps.camelize(params)
    else:
        params = {}

    assert params is not None

    # requests just simply stringifies parameters, which does not work for booleans
    for param_name, param_value in params.items():
        if isinstance(param_value, bool):
            params[param_name] = "true" if param_value else "false"

    if timeout is None:
        timeout = Timeout()

    try:
        if files:
            resp = method.value(url, files=files, timeout=timeout, params=params)
        else:
            resp = method.value(url, data=json.dumps(d), timeout=timeout, headers=headers, params=params)
    except requests.exceptions.RequestException as e:
        logger.debug("Request failed.", exc_info=True)
        # TODO would be good to provide more meaningful message but the original one could be very very long
        raise RestException("Catastrophic system error.") from e

    logger.debug(resp.url)  # to see if query parameters are ok

    _handle_response(resp)

    if return_type is None:
        return None

    if issubclass(return_type, BytesIO):

        if list_return_type:
            raise NotImplementedError

        return BytesIO(resp.content)

    logger.debug(f"Response text: {resp.text}")

    try:
        resp_json = resp.json()
    except ValueError as e:
        logger.debug(f"Got invalid JSON in the response: {resp.text}")
        raise RestException("Invalid JSON.") from e

    logger.debug(f"Response json: {resp_json}")
    if isinstance(resp_json, (dict, list)):
        resp_json = humps.decamelize(resp_json)
    logger.debug(f"Decamelized json: {resp_json}")

    if list_return_type and not isinstance(resp_json, list):
        logger.debug(f"Expected list of type {return_type}, but got {resp_json}.")
        raise RestException("Response is not a list.")

    if issubclass(return_type, JsonSchemaMixin):

        if list_return_type:
            return [dataclass_from_json(item, return_type) for item in resp_json]

        else:
            assert not isinstance(resp_json, list)

            # TODO temporary workaround for bug in humps (https://github.com/nficano/humps/issues/127)
            from arcor2.data.object_type import Box

            if return_type is Box:
                resp_json["size_x"] = resp_json["sizex"]
                resp_json["size_y"] = resp_json["sizey"]
                resp_json["size_z"] = resp_json["sizez"]

            return dataclass_from_json(resp_json, return_type)

    else:  # probably a primitive

        if list_return_type:
            return [primitive_from_json(item, return_type) for item in resp_json]
        else:
            assert not isinstance(resp_json, list)
            return primitive_from_json(resp_json, return_type)


def _handle_response(resp: requests.Response) -> None:
    """Raises exception if there is something wrong with the response.

    :param resp:
    :return:
    """

    if resp.status_code >= 400:

        decoded_content = resp.content.decode()

        # here we try to handle different cases
        try:
            raise RestHttpException(str(json.loads(decoded_content)), error_code=resp.status_code)
        except json.JsonException:
            # response contains invalid JSON
            raise RestHttpException(decoded_content, error_code=resp.status_code)


def get_image(url: str) -> Image.Image:
    """Shortcut for getting an image."""

    # TODO check content type?
    try:
        return Image.open(call(Method.GET, url, return_type=BytesIO))
    except (UnidentifiedImageError, TypeError) as e:
        raise RestException("Invalid image.") from e


def download(url: str, path: str, params: OptParams = None) -> None:
    """Shortcut for saving a file to disk."""

    with call(Method.GET, url, return_type=BytesIO, params=params) as buff:
        with open(path, "wb") as file:
            file.write(buff.getvalue())
