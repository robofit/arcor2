#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from arcor2.upload_object_type import upload


def main():

    upload("arcor2.user_objects/Box")
    upload("arcor2.user_objects/Box2")
    upload("arcor2.user_objects/Tester")


if __name__ == "__main__":
    main()
