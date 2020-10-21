pex_binary(
    name = "arserver",
    sources = ["arserver.py"],
    dependencies = ["3rdparty:PyYAML", "3rdparty:Flask"],
    entry_point = "arcor2_arserver.scripts.arserver:main",
    zip_safe=False
)

pex_binary(
    name = "broadcaster",
    sources = ["broadcaster.py"],
    entry_point = "arcor2_arserver.scripts.broadcaster:main",
    zip_safe=False
)