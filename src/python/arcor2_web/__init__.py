from importlib.resources import files


def version() -> str:
    try:
        return files(__name__).joinpath("VERSION").read_text().strip()
    except OSError:
        return "0.0.0"
