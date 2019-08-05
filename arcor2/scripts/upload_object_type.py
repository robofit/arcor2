#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
from arcor2.object_types.upload import upload, UploadException


def main() -> None:

    try:
        arg = sys.argv[1]
    except IndexError:
        print("Usage: arcor2_upload_object_type.py package.module/Cls")
        return

    try:
        upload(arg)
    except UploadException as e:
        print(e)
        return
    print('Done')


if __name__ == "__main__":
    main()
