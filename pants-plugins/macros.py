def arcor2_setup_py(**kwargs):

    if "license" not in kwargs:
        kwargs["license"] = "LGPL"

    if "author" not in kwargs:
        kwargs["author"] = "Robo@FIT"

    if "author_email" not in kwargs:
        kwargs["author_email"] = "imaterna@fit.vut.cz"

    if "classifiers" not in kwargs:
        kwargs["classifiers"] = [
                "Development Status :: 3 - Alpha",
                "Intended Audience :: Developers",
                "Topic :: Software Development :: Build Tools",
                "License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)",
                "Programming Language :: Python :: 3.8",
                "Natural Language :: English",
                "Topic :: Scientific/Engineering"
            ]

    kwargs["python_requires"] = "==3.8.*"  # we support only Python 3.8

    return setup_py(**kwargs)


def arcor2_python_distribution(**kwargs):

    if "setup_py_commands" not in kwargs:
        kwargs["setup_py_commands"] = ["sdist", "bdist_wheel", "--python-tag", "py38"]

    return python_distribution(**kwargs)


def arcor2_pex_binary(**kwargs):

    if "entry_point" not in kwargs:
        kwargs["entry_point"] = ":main"

    if "zip_safe" not in kwargs:
        kwargs["zip_safe"] = False

    if "sources" not in kwargs:
        kwargs["sources"] = [f"{kwargs['name']}.py"]

    return pex_binary(**kwargs)
