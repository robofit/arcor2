#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from arcor2.services.upload import upload_cls
import arcor2.service_types_utils as stu


def main():

    for _, srv_def in stu.built_in_services():
        upload_cls(srv_def)


if __name__ == "__main__":
    main()
