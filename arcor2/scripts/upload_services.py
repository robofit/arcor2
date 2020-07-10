#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import arcor2.service_types_utils as stu
from arcor2.services.upload import upload_cls


def main() -> None:

    for _, srv_def in stu.built_in_services():
        upload_cls(srv_def)


if __name__ == "__main__":
    main()
