"""
proxy_auth.py

This module provides functionality for setting up proxy authentication 
in a browser automation environment using the `nodriver` library.

Functions:
    setup_proxy(username: str, password: str, tab: core.tab) -> None:
        Configures a proxy by handling authentication challenges and 
        paused requests during network fetch operations.

Usage:
    Call `setup_proxy` with the proxy credentials (username and password) 
    and the browser tab instance to enable authenticated proxy connections.
"""

import asyncio

from nodriver import core
from nodriver.cdp import fetch


async def setup_proxy(username: str, password: str, tab: core.tab) -> None:
    """
    Configures proxy authentication for a browser tab by handling
    authentication challenges and paused requests.

    Parameters:
        username (str): Proxy username for authentication.
        password (str): Proxy password for authentication.
        tab (core.tab): The browser tab instance where proxy settings are applied.

    Usage:
        Call this function with valid proxy credentials and a tab instance
        to enable seamless proxy authentication for automated browsing sessions.
    """

    async def auth_challenge_handler(event: fetch.AuthRequired):
        """Handles authentication challenges by providing proxy credentials."""
        print("Auth challenge handler called")
        await tab.send(
            fetch.continue_with_auth(
                request_id=event.request_id,
                auth_challenge_response=fetch.AuthChallengeResponse(
                    response="ProvideCredentials",
                    username=username,
                    password=password,
                ),
            )
        )

    async def req_paused(event: fetch.RequestPaused):
        """Resumes paused requests during network operations."""
        await tab.send(fetch.continue_request(request_id=event.request_id))

    # Add handlers for fetch events
    tab.add_handler(
        fetch.RequestPaused, lambda event: asyncio.create_task(req_paused(event))
    )
    tab.add_handler(
        fetch.AuthRequired,
        lambda event: asyncio.create_task(auth_challenge_handler(event)),
    )

    # Enable fetch with authentication handling
    await tab.send(fetch.enable(handle_auth_requests=True))
