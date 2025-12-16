import inspect

from arcor2.docstring import parse_docstring
from arcor2_object_types.abstract import Generic
from arcor2_object_types.utils import iterate_over_actions


def sentence_like(s: str) -> None:
    assert s[0].isupper()
    assert s[-1] == "."
    assert len(s.split(" ")) > 1


def docstrings(type_def: type[Generic]) -> None:
    """Make sure that all actions are properly documented."""

    ignored_parameters = {"self", "an"}

    for _, method in iterate_over_actions(type_def):
        d = parse_docstring(method.__doc__)
        sig = inspect.signature(method)

        assert d.short_description
        sentence_like(d.short_description)

        param_names = sig.parameters.keys() - ignored_parameters

        if not param_names:
            assert d.params is None
            continue

        assert d.params
        assert d.params.keys() == param_names

        for param_name in param_names:
            assert param_name in d.params
            sentence_like(d.params[param_name])
