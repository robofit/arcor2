from typing import Optional, List, Dict, Callable
import json
import asyncio
import websockets


def response(resp_to: str, result: bool = True, messages: Optional[List[str]] = None) -> Dict:

    if messages is None:
        messages = []

    return {"response": resp_to, "result": result, "messages": messages}


def rpc(logger):
    def rpc_inner(f: Callable) -> Callable:
        async def wrapper(req: str, ui, args: Dict, req_id: Optional[int] = None):

            msg = await f(req, ui, args)
            if req_id is not None:
                msg["req_id"] = req_id
            j = json.dumps(msg)
            await asyncio.wait([ui.send(j)])
            await logger.debug(f"RPC request: {req}, args: {args}: {req_id}, result: {j}")

        return wrapper
    return rpc_inner


async def server(client, path, logger, register, unregister, rpc_dict: Dict, event_dict: Optional[Dict] = None) -> None:

    if event_dict is None:
        event_dict = {}

    await register(client)
    try:
        async for message in client:

            try:
                data = json.loads(message)
            except json.decoder.JSONDecodeError as e:
                await logger.error(e)
                continue

            if "request" in data:  # ...then it is RPC
                try:
                    rpc_func = rpc_dict[data['request']]
                except KeyError as e:
                    await logger.error(f"Unknown RPC request: {e}.")
                    continue

                await rpc_func(data['request'], client, data.get("args", {}), data.get("req_id", None))

            elif "event" in data:  # ...event from UI

                try:
                    event_func = event_dict[data["event"]]
                except KeyError as e:
                    await logger.error(f"Unknown event type: {e}.")
                    continue

                await event_func(client, data["data"])

            else:
                await logger.error(f"unsupported format of message: {data}")
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        await unregister(client)