# arcor2_logger

The service provides logging capabilities through the network. Logging-related methods are added to ObjectTypes using a mixin class.

- Messages are sent using the websockets protocol.
- Calls to `log_` methods are non-blocking.

## Example usage

```python
from typing import Optional

from arcor2_object_types.abstract import Generic, Settings

try:
    from .logging_mixin import LoggingMixin  # this is used within an execution package
except ImportError:
    from arcor2_logger.object_types.logging_mixin import LoggingMixin  # this is used during development
    
class MyObject(LoggingMixin, Generic):

    _ABSTRACT = False

    def __init__(self, obj_id: str, name: str, settings: Optional[Settings] = None) -> None:
        super().__init__(obj_id, name, settings)
        self.logger = self.get_logger()
        self.logger.info("Initialized.")
```

## Environment variables

- `ARCOR2_LOGGER_URL=ws://0.0.0.0:8765` - by default, the service listens on port 8765.
- `ARCOR2_LOGGER_LEVEL=info` - by default, messages from objects with level `info` and higher are logged.
  - Other possible values are `warning`, `error` and `debug`. 
- `ARCOR2_LOGGER_DEBUG=1` - switches logger to the `DEBUG` level.
- `ARCOR2_LOGGER_ASYNCIO_DEBUG=1` - turns on `asyncio` debug output (helpful to debug problems related to concurrency).