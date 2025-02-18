"""
tiktok_login.py

This module provides functions to automate the login process for TikTok using an email 
and password.

Main Features:
- Automates the login process using email and password.
- Handles UI navigation for various login options.
- Logs success or failure at each step of the login process.

Dependencies:
- `nodriver.core` for browser automation.
- `config_loader` for loading configuration.
- `asyncio` for asynchronous operations.

Functions:
- `log_in_email`: Automates the TikTok login process using email and password.
"""

import asyncio
import logging

from nodriver import core
from config_loader import load_config


async def log_in_email(tab: core.tab, email: str, password: str) -> bool:
    """
    Attempt to log in to TikTok using email and password.
    Returns True if login appears successful, False otherwise.
    """
    try:
        config = load_config()
        USE_PROXY = config.USE_PROXY  # Get USE_PROXY from loaded config
        
        # Click login button
        await asyncio.sleep(10) if USE_PROXY else await asyncio.sleep(3)
        login_button = await tab.find("Log in", best_match=True, timeout=60)
        if login_button:
            await login_button.click()
            await asyncio.sleep(10) if USE_PROXY else await asyncio.sleep(3)
        else:
            logging.error("Login button not found.")
            return False

        # Click "Use email / username"
        logging.info("Looking for primary email login option...")
        email_option = await tab.find("Use phone / email / username", best_match=True, timeout=60) or await tab.find("Use email / username", best_match=True, timeout=60)
        if email_option:
            logging.info("Found primary email login option, clicking...")
            await email_option.click()
            await asyncio.sleep(10) if USE_PROXY else await asyncio.sleep(3)
            logging.info("Clicked primary email login option")
        else:
            logging.info("Primary email login option not found, trying alternate...")
            
        alt_email_option = await tab.find("Log in with email or username", best_match=True, timeout=60)
        if alt_email_option:
            logging.info("Found alternate email login option, clicking...")
            await alt_email_option.click() 
            await asyncio.sleep(10) if USE_PROXY else await asyncio.sleep(3)
            logging.info("Clicked email login option")
        else:
            logging.error("No email login options found")
            return False

        # Enter email
        logging.info("Entering email...")
        try:
            email_input = await tab.select('input[name="username"]', timeout=30)
            logging.info("Email input field found - type %s", type(email_input))
            if not email_input:
                email_input = await tab.select('input[name="email"]', timeout=30)
            if email_input:
                await email_input.send_keys(email)
                await asyncio.sleep(5) if USE_PROXY else await asyncio.sleep(2)
            else:
                logging.error("Email input field not found.")
                return False
        except Exception as e:
            logging.error("Error entering email: %s", str(e))
            return False

        # Enter password
        password_input = await tab.select('input[type="password"]', timeout=60)
        if password_input:
            logging.info("Password input field found - type %s", type(password_input))
            await password_input.send_keys(password)
            await asyncio.sleep(5) if USE_PROXY else await asyncio.sleep(2)
        else:
            logging.error("Password input field not found.")
            return False

        # Click submit
        submit_button = await tab.select("button[data-e2e='login-button']", timeout=60)
        if submit_button:
            await submit_button.click()
            await asyncio.sleep(30) if USE_PROXY else await asyncio.sleep(10)
        else:
            logging.error("Submit button not found.")
            return

        logging.info("Login process completed successfully.")
        return True
        
    except Exception as e:
        logging.error("Error during TikTok login: %s", str(e))
        return False
