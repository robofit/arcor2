from arcor2.cached import CachedProject, CachedScene, UpdateableCachedProject, UpdateableCachedScene
from arcor2.data.common import Project, Scene


def test_slots() -> None:
    """Tests whether classes from cached module uses __slots__."""

    s = Scene("")
    p = Project("", s.id)

    assert not hasattr(CachedScene(s), "__dict__")
    assert not hasattr(CachedProject(p), "__dict__")
    assert not hasattr(UpdateableCachedScene(s), "__dict__")
    assert not hasattr(UpdateableCachedProject(p), "__dict__")
