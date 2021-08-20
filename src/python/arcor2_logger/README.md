# arcor2_logger

The service provides logging capabilities through the network. Logging-related methods are added to ObjectTypes using a mixin class.

- Messages are sent using the websocket protocol.
- Call to `log_` methods are non-blocking.
- The logging level for messages from ObjectTypes can be set using `ARCOR2_LOGGER_LEVEL`. Default level is `info` and other possible values are `warning`, `error` and `debug`.
- The connection string / port where the service is running is set using `ARCOR2_LOGGER_URL`, which has the following default value `ws://0.0.0.0:8765`.

## Example usage

```python
from typing import Optional

from arcor2.object_types.abstract import Generic, Settings

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
