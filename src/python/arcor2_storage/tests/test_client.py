from arcor2_storage import client


def test_create_asset_passes_upsert(monkeypatch) -> None:
    captured: dict[str, dict[str, str] | None] = {}

    def fake_call(
        method: object,
        url: str,
        *,
        params: dict[str, str] | None = None,
        files: dict[str, object] | None = None,
        return_type: object = None,
        **kwargs: object,
    ) -> None:
        captured["params"] = params
        return None

    monkeypatch.setattr(client.rest, "call", fake_call)

    client.create_asset("asset-id", b"data", description="desc", upsert=False)

    params = captured["params"]
    assert params is not None
    assert params["upsert"] == "false"
    assert params["id"] == "asset-id"
    assert params["description"] == "desc"
