from arcor2.data.common import StrEnum


class RobotType(StrEnum):

    ARTICULATED = "articulated"  # typically a 6 DoF robot
    CARTESIAN = "cartesian"
    SCARA = "scara"  # ...or scara-like
