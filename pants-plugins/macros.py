def arcor2_setup_py(**kwargs):

    if "license" not in kwargs:
        kwargs["license"] = "LGPL",

    if "author" not in kwargs:
        kwargs["author"] = "Robo@FIT",

    if "author_email" not in kwargs:
        kwargs["author_email"] = "imaterna@fit.vut.cz",

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

    return setup_py(**kwargs)
