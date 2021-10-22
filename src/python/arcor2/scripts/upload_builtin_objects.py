#!/usr/bin/env python3

from arcor2.object_types.flow_actions import FlowActions
from arcor2.object_types.logic_actions import LogicActions
from arcor2.object_types.random_actions import RandomActions
from arcor2.object_types.time_actions import TimeActions
from arcor2.object_types.upload import upload_def


def main() -> None:

    upload_def(FlowActions)
    upload_def(LogicActions)
    upload_def(TimeActions)
    upload_def(RandomActions)


if __name__ == "__main__":
    main()
