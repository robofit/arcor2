python_binary(
    name = "arserver",
    sources = ["arserver.py"],
    dependencies = ["3rdparty:PyYAML", "3rdparty:Flask"],
    entry_point = "arcor2_arserver.scripts.arserver",
    zip_safe=False
)

python_binary(
    name = "broadcaster",
    sources = ["broadcaster.py"],
    entry_point = "arcor2_arserver.scripts.broadcaster",
    zip_safe=False
)