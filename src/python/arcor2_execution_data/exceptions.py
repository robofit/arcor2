import sys
import time
import traceback

from arcor2.data.events import ProjectException
from arcor2.exceptions import Arcor2Exception


def format_stacktrace() -> str:
    parts = ["Traceback (most recent call last):\n"]
    parts.extend(traceback.format_stack(limit=25)[:-2])
    parts.extend(traceback.format_exception(*sys.exc_info())[1:])
    return "".join(parts)


def print_exception(e: Exception) -> None:
    """This is intended to be called from the main script. It prints out
    exception in form of JSON (ProjectException).

    The related traceback is saved to a text file for latter diagnosis.
    :param e: Exception to be printed out.
    :return:
    """

    pee = ProjectException(ProjectException.Data(str(e), e.__class__.__name__, isinstance(e, Arcor2Exception)))
    print(pee.to_json())
    sys.stdout.flush()

    with open("traceback-{}.txt".format(time.strftime("%Y%m%d-%H%M%S")), "w") as tb_file:
        tb_file.write(format_stacktrace())
