import pytest

from arcor2.data.object_type import Box, Cylinder, Sphere
from arcor2.exceptions import Arcor2Exception


@pytest.mark.parametrize(
    "dim",
    [[1, 1, 1], [0, 1, 1], [1, 1, 0]],
)
def test_box_valid_dimensions(dim: list[float]) -> None:
    Box("", *dim)


@pytest.mark.parametrize(
    "dim",
    [[0, 0, 1], [0, 0, 0], [-1, 1, 1], [-1, -1, -1], [-1, 0, -1]],
)
def test_box_invalid_dimensions(dim: list[float]) -> None:
    with pytest.raises(Arcor2Exception):
        Box("", *dim)


@pytest.mark.parametrize(
    "dim",
    [[1, 1]],
)
def test_cylinder_valid_dimensions(dim: list[float]) -> None:
    Cylinder("", *dim)


@pytest.mark.parametrize(
    "dim",
    [[0, 0], [0, 1], [-1, 1], [-1, -1], [-1, 0]],
)
def test_cylinder_invalid_dimensions(dim: list[float]) -> None:
    with pytest.raises(Arcor2Exception):
        Cylinder("", *dim)


@pytest.mark.parametrize(
    "dim",
    [1],
)
def test_sphere_valid_dimensions(dim: float) -> None:
    Sphere("", dim)


@pytest.mark.parametrize(
    "dim",
    [0, -1],
)
def test_sphere_invalid_dimensions(dim: float) -> None:
    with pytest.raises(Arcor2Exception):
        Sphere("", dim)
