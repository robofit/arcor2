from arcor2 import docstring


class TestType:
    """Short description.

    Long description.
    """

    def method(self, param1: int, param2: str, param3: bool) -> None:
        """Method.

        :param param1: p1
        :param param2: p2
        :param param3: p3
        :return:
        """


def test_class_docstring() -> None:
    d = docstring.parse_docstring(TestType.__doc__)

    assert d.short_description == "Short description."
    assert d.returns is None
    assert d.params is None


def test_method_docstring() -> None:
    d = docstring.parse_docstring(TestType.method.__doc__)

    assert d.short_description == "Method."
    assert d.returns is None
    assert d.params is not None
    assert d.params["param1"] == "p1"
    assert d.params["param2"] == "p2"
    assert d.params["param3"] == "p3"
