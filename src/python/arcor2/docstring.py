# Copyright 2015: Mirantis Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

# Taken from https://github.com/openstack/rally/blob/master/rally/common/plugin/info.py

import re
import sys
from dataclasses import dataclass

PARAM_OR_RETURNS_REGEX = re.compile(":(?:param|returns)")
RETURNS_REGEX = re.compile(":returns: (?P<doc>.*)", re.S)
PARAM_REGEX = re.compile(r":param (?P<name>[\*\w]+): (?P<doc>.*?)" r"(?:(?=:param)|(?=:return)|(?=:raises)|\Z)", re.S)


@dataclass
class Docstring:
    short_description: None | str = None
    long_description: None | str = None
    params: None | dict[str, str] = None
    returns: None | str = None

    def param(self, name: str) -> None | str:

        if not self.params:
            return None

        return self.params.get(name, None)


def trim(docstring: str) -> str:
    """trim function from PEP-257."""

    # Convert tabs to spaces (following the normal Python rules)
    # and split into a list of lines:
    lines = docstring.expandtabs().splitlines()
    # Determine minimum indentation (first line doesn't count):
    indent = sys.maxsize
    for line in lines[1:]:
        if stripped := line.lstrip():
            indent = min(indent, len(line) - len(stripped))
    # Remove indentation (first line is special):
    trimmed = [lines[0].strip()]
    if indent < sys.maxsize:
        for line in lines[1:]:
            trimmed.append(line[indent:].rstrip())
    # Strip off trailing and leading blank lines:
    while trimmed and not trimmed[-1]:
        trimmed.pop()
    while trimmed and not trimmed[0]:
        trimmed.pop(0)

    # Current code/unittests expects a line return at
    # end of multiline docstrings
    # workaround expected behavior from unittests
    if "\n" in docstring:
        trimmed.append("")

    # Return a single string:
    return "\n".join(trimmed)


def reindent(string: str) -> str:
    return "\n".join(line.strip() for line in string.strip().split("\n"))


def parse_docstring(docstring: None | str) -> Docstring:
    """Parse the docstring into its components."""

    doc = Docstring()

    if not docstring:
        return doc

    docstring = trim(docstring.lstrip("\n"))

    lines = docstring.split("\n", 1)
    doc.short_description = lines[0]

    if len(lines) > 1:
        doc.long_description = lines[1].strip()

        params_returns_desc = None

        if match := PARAM_OR_RETURNS_REGEX.search(doc.long_description):
            long_desc_end = match.start()
            params_returns_desc = doc.long_description[long_desc_end:].strip()
            doc.long_description = doc.long_description[:long_desc_end].rstrip()

        if params_returns_desc:
            doc.params = {name: trim(doc).strip() for name, doc in PARAM_REGEX.findall(params_returns_desc)}

            if match := RETURNS_REGEX.search(params_returns_desc):
                doc.returns = reindent(match.group("doc"))

    return doc
