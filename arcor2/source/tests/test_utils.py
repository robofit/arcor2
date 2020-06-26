import inspect
import sys

from horast import parse

from arcor2.source.utils import function_implemented

module_tree = parse(inspect.getsource(sys.modules[__name__]))


def func_1() -> None:
    """
    Test subject
    :return:
    """
    return None


def func_2() -> None:
    """
    Test subject
    :return:
    """

    raise NotImplementedError("This function is not implemented.")


def func_3() -> None:

    var = 1+2
    raise NotImplementedError(f"{var}")


def func_4(param: int) -> bool:
    """
    Exceptions different from NotImplementedError are ok.
    :param param:
    :return:
    """

    if param == 1:
        raise Exception("Exception!")
    return True


def func_5() -> None:
    raise NotImplementedError


def func_6() -> None:
    raise NotImplementedError(1)


def test_function_implemented():

    assert function_implemented(module_tree, func_1.__name__)
    assert not function_implemented(module_tree, func_2.__name__)
    assert not function_implemented(module_tree, func_3.__name__)
    assert function_implemented(module_tree, func_4.__name__)
    assert not function_implemented(module_tree, func_5.__name__)
    assert not function_implemented(module_tree, func_6.__name__)
