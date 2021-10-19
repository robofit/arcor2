# arcor2_execution

## Environment variables

- `ARCOR2_EXECUTION_URL=ws://0.0.0.0:6790` - by default, the service listens on port 6790.
- `ARCOR2_MAX_RPC_DURATION=0.1` - by default, a warning is emitted when any RPC call takes longer than 0.1 second.
- `ARCOR2_EXECUTION_DEBUG=1` - switches logger to the `DEBUG` level.
- `ARCOR2_ARSERVER_ASYNCIO_DEBUG=1` - turns on `asyncio` debug output (helpful to debug problems related to concurrency).