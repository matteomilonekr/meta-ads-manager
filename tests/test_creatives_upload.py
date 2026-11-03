"""Tests for upload_image: local files (path checks, limits, errors), safety guard and URL regression."""

from types import SimpleNamespace

import httpx
import pytest
import respx

from meta_ads_mcp.auth import AuthManager, MetaAuthConfig
from meta_ads_mcp.client import MetaAdsClient
from meta_ads_mcp.models.common import META_GRAPH_URL
from meta_ads_mcp.tools import creatives
from meta_ads_mcp.utils.safety import safety_guard

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
OK_RESPONSE = {"images": {"cover.jpg": {"hash": "HASH1", "url": "https://u"}}}


def make_ctx() -> SimpleNamespace:
    client = MetaAdsClient(AuthManager(MetaAuthConfig(access_token="test-token")))
    return SimpleNamespace(lifespan_context={"meta_client": client})


def tool_fn(tool):
    return getattr(tool, "fn", tool)


@pytest.fixture
def recorded(monkeypatch):
    """Disable the real safety guard and collect record_write calls."""
    calls = []
    monkeypatch.setattr(safety_guard, "check_write_allowed", lambda *a: None)
    monkeypatch.setattr(safety_guard, "record_write", lambda *a: calls.append(a))
    return calls


@pytest.fixture
async def ctx():
    ctx = make_ctx()
    yield ctx
    await ctx.lifespan_context["meta_client"].close()


async def upload(ctx, **kwargs) -> str:
    return await tool_fn(creatives.upload_image)("1", ctx=ctx, **kwargs)


@respx.mock
async def test_upload_from_local_jpeg(tmp_path, recorded, ctx):
    img = tmp_path / "cover.jpg"
    img.write_bytes(JPEG)
    route = respx.post(f"{META_GRAPH_URL}/act_1/adimages").mock(return_value=httpx.Response(200, json=OK_RESPONSE))
    out = await upload(ctx, file_path=str(img))
    assert "HASH1" in out
    assert "bytes=" in route.calls[0].request.content.decode()
    assert recorded == [("create", "act_1")]


@respx.mock
async def test_upload_from_local_png_with_png_extension(tmp_path, recorded, ctx):
    img = tmp_path / "cover.png"
    img.write_bytes(PNG)
    respx.post(f"{META_GRAPH_URL}/act_1/adimages").mock(return_value=httpx.Response(200, json=OK_RESPONSE))
    assert "HASH1" in await upload(ctx, file_path=str(img))


@respx.mock
async def test_missing_file_and_wrong_extension_are_rejected(tmp_path, recorded, ctx):
    route = respx.post(f"{META_GRAPH_URL}/act_1/adimages").mock(return_value=httpx.Response(200, json=OK_RESPONSE))
    txt = tmp_path / "a.txt"
    txt.write_bytes(JPEG)
    assert (await upload(ctx, file_path=str(txt))).startswith("Error")
    assert (await upload(ctx, file_path=str(tmp_path / "missing.jpg"))).startswith("Error")
    assert (await upload(ctx, file_path=str(tmp_path))).startswith("Error")  # a directory
    assert not route.called
    assert recorded == []


async def test_neither_param_is_an_error(recorded, ctx):
    assert (await upload(ctx)).startswith("Error")


@respx.mock
async def test_symlink_is_rejected(tmp_path, recorded, ctx):
    real = tmp_path / "real.jpg"
    real.write_bytes(JPEG)
    link = tmp_path / "link.jpg"
    link.symlink_to(real)
    route = respx.post(f"{META_GRAPH_URL}/act_1/adimages").mock(return_value=httpx.Response(200, json=OK_RESPONSE))
    out = await upload(ctx, file_path=str(link))
    assert out.startswith("Error") and "symbolic" in out
    assert not route.called


@respx.mock
async def test_empty_file_is_rejected(tmp_path, recorded, ctx):
    img = tmp_path / "empty.jpg"
    img.write_bytes(b"")
    route = respx.post(f"{META_GRAPH_URL}/act_1/adimages").mock(return_value=httpx.Response(200, json=OK_RESPONSE))
    out = await upload(ctx, file_path=str(img))
    assert out.startswith("Error") and "empty" in out
    assert not route.called


@respx.mock
async def test_non_image_bytes_with_image_extension_are_rejected(tmp_path, recorded, ctx):
    fake = tmp_path / "secret.jpg"
    fake.write_bytes(b"-----BEGIN PRIVATE KEY-----\nTOPSECRET\n")
    route = respx.post(f"{META_GRAPH_URL}/act_1/adimages").mock(return_value=httpx.Response(200, json=OK_RESPONSE))
    out = await upload(ctx, file_path=str(fake))
    assert out.startswith("Error") and "JPEG or PNG" in out
    assert "TOPSECRET" not in out
    assert not route.called


@respx.mock
async def test_file_over_10_mb_is_rejected(tmp_path, recorded, ctx):
    big = tmp_path / "big.jpg"
    with big.open("wb") as f:
        f.write(JPEG)  # valid magic bytes: only the size check can reject it
        f.truncate(10 * 1024 * 1024 + 1)  # sparse, nothing real is written
    route = respx.post(f"{META_GRAPH_URL}/act_1/adimages").mock(return_value=httpx.Response(200, json=OK_RESPONSE))
    out = await upload(ctx, file_path=str(big))
    assert out.startswith("Error") and "10 MB" in out
    assert not route.called


@respx.mock
async def test_file_of_exactly_10_mb_is_accepted(tmp_path, recorded, ctx):
    img = tmp_path / "limit.jpg"
    with img.open("wb") as f:
        f.write(JPEG)
        f.truncate(10 * 1024 * 1024)
    respx.post(f"{META_GRAPH_URL}/act_1/adimages").mock(return_value=httpx.Response(200, json=OK_RESPONSE))
    assert "HASH1" in await upload(ctx, file_path=str(img))


@respx.mock
async def test_upload_dir_restricts_paths(tmp_path, monkeypatch, recorded, ctx):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    inside = allowed / "ok.jpg"
    inside.write_bytes(JPEG)
    outside = tmp_path / "outside.jpg"
    outside.write_bytes(JPEG)
    respx.post(f"{META_GRAPH_URL}/act_1/adimages").mock(return_value=httpx.Response(200, json=OK_RESPONSE))
    monkeypatch.setenv("META_UPLOAD_DIR", str(allowed))
    assert "HASH1" in await upload(ctx, file_path=str(inside))
    out = await upload(ctx, file_path=str(outside))
    assert out.startswith("Error") and "META_UPLOAD_DIR" in out
    # '..' traversal is resolved before the check
    out = await upload(ctx, file_path=str(allowed / ".." / "outside.jpg"))
    assert out.startswith("Error") and "META_UPLOAD_DIR" in out


@respx.mock
async def test_symlinked_parent_cannot_escape_upload_dir(tmp_path, monkeypatch, recorded, ctx):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "x.jpg").write_bytes(JPEG)
    (allowed / "dir").symlink_to(elsewhere)
    monkeypatch.setenv("META_UPLOAD_DIR", str(allowed))
    out = await upload(ctx, file_path=str(allowed / "dir" / "x.jpg"))
    assert out.startswith("Error") and "META_UPLOAD_DIR" in out


@respx.mock
async def test_meta_error_on_file_branch_returns_error_string(tmp_path, recorded, ctx):
    img = tmp_path / "cover.jpg"
    img.write_bytes(JPEG)
    respx.post(f"{META_GRAPH_URL}/act_1/adimages").mock(
        return_value=httpx.Response(400, json={"error": {"code": 100, "message": "Invalid parameter"}})
    )
    out = await upload(ctx, file_path=str(img))
    assert out.startswith("Error")
    assert "Invalid parameter" in out
    assert recorded == []  # failed upload is not recorded as a write


async def test_os_error_on_file_branch_returns_error_string(tmp_path, monkeypatch, recorded, ctx):
    img = tmp_path / "cover.jpg"
    img.write_bytes(JPEG)

    def boom(self):
        raise PermissionError("denied")

    monkeypatch.setattr(creatives.Path, "read_bytes", boom)
    out = await upload(ctx, file_path=str(img))
    assert out.startswith("Error")
    assert recorded == []


@respx.mock
async def test_both_params_is_an_error(tmp_path, recorded, ctx):
    img = tmp_path / "cover.jpg"
    img.write_bytes(JPEG)
    route = respx.post(f"{META_GRAPH_URL}/act_1/adimages").mock(return_value=httpx.Response(200, json=OK_RESPONSE))
    out = await upload(ctx, image_url="https://example.com/a.jpg", file_path=str(img))
    assert out.startswith("Error") and "not both" in out
    assert not route.called


@respx.mock
@pytest.mark.parametrize("kwargs", [{"image_url": "https://example.com/a.jpg"}, {"file_path": "FILE"}])
async def test_safety_guard_blocks_before_any_io(tmp_path, monkeypatch, ctx, kwargs):
    img = tmp_path / "cover.jpg"
    img.write_bytes(JPEG)
    recorded = []
    monkeypatch.setattr(safety_guard, "check_write_allowed", lambda *a: "troppe scritture")
    monkeypatch.setattr(safety_guard, "record_write", lambda *a: recorded.append(a))
    # fail the test if the file is read
    monkeypatch.setattr(creatives.Path, "read_bytes", lambda self: pytest.fail("file read despite guard"))
    route = respx.route().mock(return_value=httpx.Response(200, json=OK_RESPONSE))
    kwargs = {k: (str(img) if v == "FILE" else v) for k, v in kwargs.items()}
    out = await upload(ctx, **kwargs)
    assert "Operazione bloccata" in out and "troppe scritture" in out
    assert not route.called
    assert recorded == []


@respx.mock
async def test_url_branch_still_uploads_by_url(recorded, ctx):
    route = respx.post(f"{META_GRAPH_URL}/act_1/adimages").mock(return_value=httpx.Response(200, json=OK_RESPONSE))
    out = await upload(ctx, image_url="https://example.com/a.jpg")
    assert "HASH1" in out
    assert "url=" in route.calls[0].request.content.decode()
    assert recorded == [("create", "act_1")]


@respx.mock
async def test_url_branch_falls_back_to_bytes(recorded, ctx):
    posts = respx.post(f"{META_GRAPH_URL}/act_1/adimages").mock(
        side_effect=[
            httpx.Response(400, json={"error": {"code": 100, "message": "bad url"}}),
            httpx.Response(200, json=OK_RESPONSE),
        ]
    )
    respx.get("https://example.com/a.jpg").mock(return_value=httpx.Response(200, content=JPEG))
    out = await upload(ctx, image_url="https://example.com/a.jpg")
    assert "HASH1" in out
    assert "bytes=" in posts.calls[1].request.content.decode()
    assert recorded == [("create", "act_1")]


@respx.mock
@pytest.mark.parametrize(
    "url",
    ["http://localhost/a.jpg", "http://127.0.0.1/a.jpg", "http://169.254.169.254/latest", "file:///etc/passwd"],
)
async def test_url_branch_still_blocks_ssrf(recorded, ctx, url):
    route = respx.route().mock(return_value=httpx.Response(200, json=OK_RESPONSE))
    with pytest.raises(ValueError):
        await upload(ctx, image_url=url)
    assert not route.called
    assert recorded == []
