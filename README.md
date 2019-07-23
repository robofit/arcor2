# ARCOR2

Expected environment:
  * Ubuntu 18.04
  * Python 3.6
  * ...dependencies from setup.py
  
Installation (for development):
```bash
pip3 install -e .
```

Commands:
  * ```arcor2_server```
  * ```arcor2_manager```
  * ```arcor2_upload_ot```

Before running ```arcor2_manager```, please set ```ARCOR2_PROJECT_PATH``` to a directory in ```PYTHONPATH```.

How to run tests:
```bash
mypy arcor2
flake8 arcor2
py.test arcor2
```

