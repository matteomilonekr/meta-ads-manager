"""FastMCP server for Meta Ads API."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastmcp import FastMCP

from meta_ads_mcp.auth import load_config_from_env, AuthManager
from meta_ads_mcp.client import MetaAdsClient

logger = logging.getLogger(__name__)

SERVER_NAME = "meta_ads_mcp"


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Initialize Meta Ads client at server startup.

    Yields a dict with 'meta_client' and 'auth' keys.
    Tools access via ctx.request_context.lifespan_state["meta_client"].
    """
    logger.info("Initializing Meta Ads MCP server...")
    config = load_config_from_env()
    auth = AuthManager(config)
    client = MetaAdsClient(auth)

    logger.info("Meta Ads client initialized.")
    try:
        yield {"meta_client": client, "auth": auth}
    finally:
        await client.close()
        logger.info("Meta Ads MCP server shut down.")


def create_server() -> FastMCP:
    """Create and configure the FastMCP server instance."""
    server = FastMCP(SERVER_NAME, lifespan=app_lifespan)
    return server


# Module-level server instance — tools register on this via @mcp.tool()
mcp = create_server()

# Import tools module to trigger @mcp.tool() registration
import meta_ads_mcp.tools  # noqa: E402, F401


def main() -> None:
    """Entry point for running the server."""
    mcp.run()


if __name__ == "__main__":
    main()
