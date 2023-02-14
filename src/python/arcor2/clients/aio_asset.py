from arcor2.clients import asset
from arcor2.helpers import run_in_executor


async def asset_info() -> list[asset.AssetInfo]:
    return await run_in_executor(asset.asset_info)


async def asset_ids() -> set[str]:
    return await run_in_executor(asset.asset_ids)


async def delete_asset(id: str, remove_dependers: bool = False) -> None:
    await run_in_executor(asset.delete_asset, id, remove_dependers)


async def asset_exists(id: str) -> bool:
    return await run_in_executor(asset.asset_exists, id)
