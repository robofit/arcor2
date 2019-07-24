# ARCOR2

[![CircleCI](https://circleci.com/gh/robofit/arcor2.svg?style=svg&circle-token=190cc70ee7baa7b6b1335f85ff71a553cf2c50a2)](https://circleci.com/gh/robofit/arcor2)

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
mypy --strict arcor2
flake8 arcor2
py.test --cov arcor2
```

After any commit, coverage should not be worse than before.

