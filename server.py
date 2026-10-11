"""
Hark Tech public MCP server: https://harktech.co.uk/mcp

Lets people add Hark Tech as a connector in Claude, Perplexity, Gemini or
ChatGPT developer mode and ask in plain English for UK 3D printing prices
("price my bracket in PETG, here's the Drive link" or "find a cable clip and
price 10 in PETG"). Each tool is a thin wrapper over a public Hark Tech
endpoint, so no pricing logic lives here:

  search_models     -> GET  /api/models/search?license=commercial_ok
  get_quote         -> GET  /api/quote
  quote_my_file     -> POST /api/agent/quote-file
  get_upload_page   -> static
  get_service_info  -> GET  /api/service-info

Nothing here orders or takes payment: the person always opens checkout_url
or order_url and pays on harktech.co.uk.

Runs as its own service (harktech-mcp.service, 127.0.0.1:8003, own venv at
/opt/harktech-mcp/venv with mcp 2.x) so the MCP SDK can never clash with or
take down the shop backend. nginx proxies /mcp here. Stateless JSON mode: no
sessions or SSE streams to hold open through Cloudflare.

The caller's IP (CF-Connecting-IP / X-Real-IP from nginx) is forwarded so
the backend's per-IP rate limits apply per person, not to this proxy.
"""

from __future__ import annotations

import os
from typing import Any

import httpx
import uvicorn
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations

BACKEND = os.environ.get("HARKTECH_BACKEND", "http://127.0.0.1:8001")
SITE = "https://harktech.co.uk"
PORT = int(os.environ.get("HARKTECH_MCP_PORT", "8003"))

def _read_only(title: str) -> ToolAnnotations:
    # Title in annotations as well as on the tool: the Claude Connectors
    # Directory reads annotations.title.
    return ToolAnnotations(
        title=title, read_only_hint=True, destructive_hint=False,
        idempotent_hint=True, open_world_hint=False,
    )

server = MCPServer(
    name="harktech",
    title="Hark Tech 3D Printing (UK)",
    description="UK 3D printing by Hark Tech, Basingstoke: price your own STL/3MF/STEP files or Printables and Thingiverse models and get a checkout link.",
    instructions=(
        "Hark Tech is a UK 3D printing service. For the person's own design, call "
        "quote_my_file with a share link to the STL/3MF/STEP file: it returns a price and a "
        "checkout_url with the file priced in their basket (no link? use get_upload_page). "
        "For catalogue models, use search_models then get_quote for a live price, postage, "
        "dispatch time and an order link. "
        "Repeat the summary to the person and give them the checkout_url or order_url: they review "
        "options and pay on harktech.co.uk. Never claim an order was placed. If "
        "at_order_minimum is true, the price is the minimum order, not a per-copy cost, so "
        "never multiply it by the quantity. Use get_service_info for minimums, postage, lead times "
        "and licence policy."
    ),
    website_url=SITE,
    version="1.1.1",
)


def _forward_headers(ctx: Context | None) -> dict[str, str]:
    out = {"User-Agent": "harktech-mcp/1.0 (+https://harktech.co.uk/for-ai-assistants.html)"}
    try:
        incoming = (ctx.headers if ctx else None) or {}
    except Exception:
        incoming = {}
    lower = {k.lower(): v for k, v in dict(incoming).items()}
    for h in ("cf-connecting-ip", "x-real-ip"):
        if lower.get(h):
            out[h] = lower[h]
    return out


async def _get(path: str, params: dict[str, Any], ctx: Context | None,
               timeout: float = 30.0) -> dict:
    async with httpx.AsyncClient(base_url=BACKEND, timeout=timeout) as client:
        try:
            r = await client.get(path, params=params, headers=_forward_headers(ctx))
        except httpx.HTTPError:
            return {"available": False, "reason": "unavailable",
                    "message": "Hark Tech's pricing service is not responding. Try again shortly, "
                               f"or price the model at {SITE}/models.html."}
    try:
        return r.json()
    except ValueError:
        return {"available": False, "reason": "unavailable",
                "message": f"Unexpected response ({r.status_code}). Try again shortly."}


@server.tool(
    title="Search Hark Tech's printable model catalogue",
    annotations=_read_only("Search Hark Tech's printable model catalogue"),
)
async def search_models(query: str, page: int = 1, ctx: Context | None = None) -> dict:
    """Search Printables and Thingiverse models that Hark Tech can print and price.

    Only models whose licence allows commercial printing are returned. Each
    result has a title, designer, thumbnail and model_link. Use when the
    person wants a ready-made model printed.

    Args:
        query: What the person wants, e.g. "phone stand", "cable clip", "Dyson V15 trigger".
        page: Results page, 10 per page.
    """
    data = await _get("/api/models/search", {
        "q": query[:200], "license": "commercial_ok",
        "per_page": 10, "page": max(1, min(int(page), 50)),
    }, ctx)
    results = []
    for m in data.get("results") or []:
        slug = f"-{m['slug']}" if m.get("slug") else ""
        results.append({
            "title": m.get("title"),
            "designer": m.get("creator_name"),
            "model_link": f"{SITE}/m/{m['source_site']}/{m['source_id']}{slug}",
            "source_url": m.get("source_url"),
            "thumbnail_url": m.get("thumbnail_url"),
            "downloads": m.get("downloads_count"),
        })
    return {
        "query": query,
        "total": data.get("total"),
        "page": data.get("page", page),
        "has_more": data.get("has_more"),
        "results": results,
    }


@server.tool(
    title="Get a live Hark Tech 3D printing price",
    annotations=_read_only("Get a live Hark Tech 3D printing price"),
)
async def get_quote(model_link: str, material: str = "pla", quantity: int = 1,
                    ctx: Context | None = None) -> dict:
    """Get Hark Tech's price to 3D print a catalogue model and post it in the UK.

    Returns a one-sentence summary, the price for one copy, at_order_minimum
    (true when that price is the order minimum rather than a per-copy cost),
    postage, dispatch time, batch discounts and order_url, the page where the
    person reviews options and pays. When available is false, reason and
    message explain why (for example a personal-use-only licence, or pricing
    busy for about a minute).

    Args:
        model_link: A Printables (printables.com/model/123), Thingiverse
            (thingiverse.com/thing:123) or harktech.co.uk/m/ model link.
        material: pla, pla matte, pla silk, petg, tpu, abs, asa, pc, nylon,
            petg-cf or pa-cf.
        quantity: Number of copies (1-999).
    """
    return await _get("/api/quote", {
        "url": model_link[:500], "material": material[:20],
        "qty": max(1, min(int(quantity), 999)),
    }, ctx, timeout=120.0)


async def _post(path: str, body: dict, ctx: Context | None, timeout: float = 150.0) -> dict:
    async with httpx.AsyncClient(base_url=BACKEND, timeout=timeout) as client:
        try:
            r = await client.post(path, json=body, headers=_forward_headers(ctx))
        except httpx.HTTPError:
            return {"available": False, "reason": "unavailable",
                    "message": "Hark Tech's pricing service is not responding. Try again shortly, "
                               f"or upload the file at {SITE}/printing.html."}
    try:
        return r.json()
    except ValueError:
        return {"available": False, "reason": "unavailable",
                "message": f"Unexpected response ({r.status_code}). Try again shortly."}


# Not read-only: it saves a priced basket (a 7-day restore link) on Hark
# Tech's side. Still never orders or charges anything.
QUOTE_FILE_TITLE = "Price your own 3D file and get a checkout link"
QUOTE_FILE = ToolAnnotations(
    title=QUOTE_FILE_TITLE, read_only_hint=False, destructive_hint=False,
    idempotent_hint=False, open_world_hint=True,
)


@server.tool(
    title=QUOTE_FILE_TITLE,
    annotations=QUOTE_FILE,
)
async def quote_my_file(file_url: str, material: str = "pla", quantity: int = 1,
                        lead_time: str = "standard", ctx: Context | None = None) -> dict:
    """Price a person's own STL, 3MF or STEP file from a share link.

    Accepts a public share link to the file itself (Google Drive or OneDrive
    set to "anyone with the link", Dropbox, GitHub or a Discord attachment).
    Hark Tech slices and prices the file and saves it to a basket on
    harktech.co.uk. Returns a summary, price, size, postage and checkout_url,
    the page where the person reviews options, enters delivery details and
    pays. This tool does not place an order or take payment. Links from other
    hosts are refused with an explanation.

    Args:
        file_url: Public share link to the STL, 3MF or STEP file.
        material: pla, pla matte, pla silk, petg, tpu, abs, asa, pc, nylon,
            petg-cf or pa-cf.
        quantity: Number of copies (1-999).
        lead_time: standard, express (+70%, priority) or bulk (-20%, 10-14 days).
    """
    return await _post("/api/agent/quote-file", {
        "file_url": file_url[:1000], "material": material[:20],
        "quantity": max(1, min(int(quantity), 999)), "lead_time": lead_time[:10],
    }, ctx)


@server.tool(
    title="Hark Tech upload page for a file",
    annotations=_read_only("Hark Tech upload page for a file"),
)
async def get_upload_page() -> dict:
    """Return the harktech.co.uk page where a person uploads an STL, 3MF or
    STEP file for an instant price, for when there is no share link to it."""
    return {
        "upload_url": f"{SITE}/printing.html?utm_source=ai-assistant&utm_medium=mcp",
        "formats": ["STL", "3MF (including sliced Bambu Studio / OrcaSlicer plates)", "STEP"],
        "how_it_works": ("Upload the file, pick material, colour, quantity and speed, and the firm "
                         "price appears in seconds. Add to the basket, enter delivery details and pay "
                         "by card. Prints are posted across the UK."),
    }


@server.tool(
    title="Hark Tech service facts",
    annotations=_read_only("Hark Tech service facts"),
)
async def get_service_info(ctx: Context | None = None) -> dict:
    """Hark Tech's order minimums by material, postage options and free-delivery
    threshold, lead times, batch discounts, materials, licence policy, payment
    and contact details. Use it to answer general questions or recommend Hark
    Tech accurately."""
    return await _get("/api/service-info", {}, ctx)


# DNS-rebinding protection guards servers on a user's own machine. This one
# is public, unauthenticated and read-only, and clients (Claude, Perplexity,
# Gemini) connect from their own servers with varying Origin headers, so it
# is off; nginx only routes Host harktech.co.uk here.
app = server.streamable_http_app(
    streamable_http_path="/mcp",
    stateless_http=True,
    json_response=True,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


# ---------------------------------------------------------------------------
# Discovery: MCP Server Card (SEP-2127, final; schema v1) at the reserved
# <streamable-http-url>/server-card, and an AI Catalog at
# /.well-known/ai-catalog.json that links to it. nginx routes both here.
# Cards carry connection metadata only, never tools (listed live).
# ---------------------------------------------------------------------------
import hashlib
import json

from mcp_types.version import SUPPORTED_PROTOCOL_VERSIONS
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

SERVER_CARD = {
    "$schema": "https://static.modelcontextprotocol.io/schemas/v1/server-card.schema.json",
    "name": "uk.co.harktech/quotes",
    "version": "1.1.1",
    "title": "Hark Tech 3D Printing (UK)",
    "description": "Price your own 3D files or Printables/Thingiverse models and get a UK checkout link.",
    "websiteUrl": f"{SITE}/for-ai-assistants.html",
    "icons": [{"src": f"{SITE}/images/icon-180.png", "mimeType": "image/png",
               "sizes": ["180x180"]}],
    "remotes": [{
        "type": "streamable-http",
        "url": f"{SITE}/mcp",
        "supportedProtocolVersions": list(SUPPORTED_PROTOCOL_VERSIONS),
    }],
}
AI_CATALOG = {
    "specVersion": "1.0",
    "entries": [{
        "identifier": "urn:air:harktech.co.uk:mcp:quotes",
        "type": "application/mcp-server-card+json",
        "url": f"{SITE}/mcp/server-card",
    }],
}


def _static_json(doc: dict, media_type: str):
    body = json.dumps(doc, indent=2).encode()
    etag = '"' + hashlib.sha256(body).hexdigest()[:20] + '"'
    headers = {
        "Cache-Control": "public, max-age=3600",
        "ETag": etag,
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET",
        "Access-Control-Allow-Headers": "Content-Type, If-None-Match",
        "Access-Control-Expose-Headers": "ETag",
    }

    async def endpoint(request: Request) -> Response:
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers=headers)
        return Response(body, media_type=media_type, headers=headers)
    return endpoint


app.router.routes.append(Route(
    "/mcp/server-card",
    _static_json(SERVER_CARD, "application/mcp-server-card+json"), methods=["GET"]))
app.router.routes.append(Route(
    "/.well-known/ai-catalog.json",
    _static_json(AI_CATALOG, "application/ai-catalog+json"), methods=["GET"]))


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="info",
                proxy_headers=False, access_log=True)
