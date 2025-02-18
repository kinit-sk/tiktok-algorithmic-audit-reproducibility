"""
main.py

This module serves as the entry point for the TikTok scraping application. It orchestrates
the scraping workflow, including browser automation and event handling for network interception.

Key Features:
    - Initializes the browser with optional proxy and cookie reuse.
    - Logs into TikTok if required.
    - Handles cookies banners and network events.
    - Scrapes videos from the "For You" page (FYP) based on user configurations.
    - Stores data (logs, JSON files, screenshots) locally under runs/{test_run_id}.
    - Manages logs for each scraping session.

Modules and Functions:
    - `main(user_id: int, user_config: dict)`: The main function that coordinates scraping 
      for a given user.
    - `handle_cookies_banner(tab: core.tab)`: Attempts to dismiss cookie banners on the webpage.
    - `move_json_files(src_directory: str, dest_directory: str)`: Moves JSON files from one 
      directory to another (optional utility).
    - `patched_parse_json_event(json_message: dict)`: A patched version of the JSON event parser 
      to handle missing keys gracefully.
    - `set_video_batches_queue(q: asyncio.Queue)`: Sets a fresh queue for video batch processing.
    - `browse_fyp`: Scrapes videos and handles batch processing (imported from `scraper.fyp_browser`).

Configuration:
    - User-specific settings such as email, password, proxy, and scraping limits are loaded 
      from the `config.py` file.
    - The `nodriver` module is used for browser automation and network interception.

Logging:
    - Logs are captured in both the console and a temporary file (`temp.log`).
    - Logs for each session are moved to a structured folder under `runs/{test_run_id}/logs`.
    - If no test run ID is generated (e.g., code fails early), logs are saved in a fallback folder under `runs/logs_fallback`.

Requirements:
    - TikTok credentials must be configured in `config.py` if login is enabled.
    - Proxy settings, if required, must also be available in `config.py`.
    - The `nodriver` module is used for browser automation.

Usage:
    - This script can be executed directly. It processes all user profiles defined in `config.USER_PROFILES`.
    - Logs, screenshots, and JSON data are saved under a `runs/{test_run_id}` directory or a fallback logs directory.

Example:
    To start scraping for all users in the configuration:
    ```bash
    python main.py
    ```
"""

import asyncio
import logging
import os
import shutil
import time  
import importlib.util

import nodriver as uc
import nodriver.cdp.util as cdp_util
from common.proxy_auth import setup_proxy
from config_loader import load_config
from scraper.fyp_browser import browse_fyp
from scraper.tiktok_login import log_in_email
# Network interception handlers
from scraper.tiktok_network_interceptor import (
    generated_json_files,
    loading_finished_handler,
    processed_author_ids,
    processed_hashtag_ids,
    processed_music_ids,
    processed_request_ids,
    processed_video_ids,
    request_map,
    request_will_be_sent_handler,
    response_received_handler,
    set_video_batches_queue,
)

# Get unique temp log file name from environment
TEMP_LOG = os.environ.get("TEMP_LOG", "temp.log")

# Configure root logger to log both to console and to the unique file
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s:%(name)s:%(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(TEMP_LOG, mode="w", encoding="utf-8"),
    ],
)

# We patch parse_json_event to avoid KeyError in cdp_util
original_parse_json_event = cdp_util.parse_json_event


def patched_parse_json_event(json_message: dict) -> any:
    """
    Patch to avoid KeyError in parse_json_event if certain CDP keys are missing.
    """
    try:
        return original_parse_json_event(json_message)
    except KeyError:
        return None


cdp_util.parse_json_event = patched_parse_json_event


def move_json_files(src_directory, dest_directory):
    """
    Move all .json files from src_directory to dest_directory and log their names.
    (Kept as an optional utility.)
    """
    try:
        os.makedirs(dest_directory, exist_ok=True)
        moved_files = []
        for filename in os.listdir(src_directory):
            if filename.endswith(".json"):
                src_file = os.path.join(src_directory, filename)
                dest_file = os.path.join(dest_directory, filename)
                shutil.move(src_file, dest_file)
                moved_files.append(filename)
                logging.info("Moved %s to %s", filename, dest_directory)
        if moved_files:
            logging.info("Total JSON files moved in this run: %s", len(moved_files))
    except Exception as e:
        logging.error("Error moving .json files: %s", e)


async def handle_cookies_banner(tab: uc.core.tab):
    """
    Attempt to click the 'Allow all'/'Accept all' cookies button (sometimes inside shadow DOM).
    """
    await tab
    try:
        script = """
        (function() {
            function findButtonInShadowRoot(root) {
                if (!root) {
                    return null;
                }
                var walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT);
                var node;
                while ((node = walker.nextNode())) {
                    if (node.tagName === 'BUTTON') {
                        var text = node.textContent.trim();
                        if (text === 'Allow all' || text === 'Accept all') {
                            return node;
                        }
                    }
                    if (node.shadowRoot) {
                        var result = findButtonInShadowRoot(node.shadowRoot);
                        if (result) {
                            return result;
                        }
                    }
                }
                return null;
            }
            var button = findButtonInShadowRoot(document);
            if (button) {
                button.click();
                return true;
            } else {
                return false;
            }
        })();
        """

        result = await tab.evaluate(script)
        if result:
            logging.info("Clicked 'Allow all' or 'Accept all' button inside shadow DOM.")
            await asyncio.sleep(5)
        else:
            logging.info("'Allow all'/'Accept all' button not found.")
    except Exception as e:
        logging.error("Error while handling cookies banner: %s", e)
        logging.info("'Allow all'/'Accept all' button not found, proceeding.")


# Load config at the start
config = load_config()


async def main(user_id: int, user_config: dict):
    """
    Main function that:
    1) Creates/clears a fresh queue for each user
    2) Starts the browser (with or without incognito & proxy)
    3) Navigates to tiktok.com
    4) Optionally logs in
    5) Attaches event handlers for requests/responses
    6) Calls browse_fyp for scraping
    7) Cleans up (closes browser, moves logs)
    """
    browser = None
    testrun_id = None

    try:
        # Get scenario from environment as float
        scenario = float(os.environ.get("SCENARIO"))
        if not scenario:
            raise ValueError("SCENARIO environment variable not set")

        # Create a fresh queue for video batch processing
        new_queue = asyncio.Queue()
        set_video_batches_queue(new_queue)

        user_data_path = os.path.abspath(f"browser_storage/browser_data_{user_id}")
        browser_args = ["--mute-audio"]

        # Setup proxy if needed
        if config.USE_PROXY:
            try:
                browser_args.insert(0, f"--proxy-server={config.PROXY}")
            except AttributeError:
                logging.error("Proxy settings not found in config. Exiting.")
                return
        else:
            logging.info("Proxy usage is disabled.")

        # Start the browser
        if config.REUSE_COOKIES:
            browser = await uc.start(
                browser_args=browser_args,
                user_data_dir=user_data_path
            )
        else:
            browser = await uc.start(browser_args=browser_args + ["--incognito"])

        tab = await browser.get("about:blank")

        # If proxy usage requires authentication
        if config.USE_PROXY and config.PROXYUSERNAME:
            await setup_proxy(config.PROXYUSERNAME, config.PROXYPASSWORD, tab)

        # Navigate to TikTok
        tab = await browser.get("https://tiktok.com/")
        logging.info("User %s: Navigated to TikTok.", user_id)
        await asyncio.sleep(5)

        # Handle cookies banner
        await asyncio.sleep(5)
        await handle_cookies_banner(tab)

        # Log in if needed
        if config.USE_LOGIN:
            await log_in_email(tab, config.TIKTOK_EMAIL, config.TIKTOK_PASSWORD)
        else:
            logging.info("Skipping login (USE_LOGIN = False).")

        # Enable network events
        logging.info("Network tracking enabled.")
        await tab.send(uc.cdp.network.enable())

        # Attach handlers for requests/responses
        tab.add_handler(
            uc.cdp.network.RequestWillBeSent,
            lambda e: asyncio.create_task(request_will_be_sent_handler(e, tab)),
        )
        tab.add_handler(
            uc.cdp.network.ResponseReceived,
            lambda e: asyncio.create_task(response_received_handler(e, tab)),
        )
        tab.add_handler(
            uc.cdp.network.LoadingFinished,
            lambda e: asyncio.create_task(loading_finished_handler(e, tab)),
        )

        logging.info("User %s: Trying to browse up to %s videos.", user_id, config.MAX_VIDEOS)

        # Call browse_fyp with scenario
        testrun_id = await browse_fyp(
            tab=tab,
            max_batches=config.NUM_BATCHES,
            max_videos=config.MAX_VIDEOS,
            user_id=user_id,
            user_config=user_config,
            scenario=scenario,
        )

        if testrun_id:
            logging.info("browse_fyp finished with testRunID=%s", testrun_id)
        else:
            logging.info("browse_fyp returned None => no test run created?")

        # Wait for any lingering tasks
        pending = [
            task
            for task in asyncio.all_tasks()
            if task is not asyncio.current_task()
        ]
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)

        generated_json_files.clear()
        logging.info("User %s: JSON files from this run handled successfully.", user_id)

        # After getting testrun_id from browse_fyp, move the log file
        if testrun_id:
            # Use string formatting to avoid decimal point in folder name
            log_dir = f"runs/scenario_{scenario:.1f}/{testrun_id}/logs"
            os.makedirs(log_dir, exist_ok=True)
            if os.path.exists(TEMP_LOG):
                shutil.move(TEMP_LOG, os.path.join(log_dir, f"run_{user_id}.log"))

    except Exception as e:
        logging.error("Error in main for user %s: %s", user_id, e)
    finally:
        # Reset network interceptor data
        processed_request_ids.clear()
        processed_video_ids.clear()
        processed_author_ids.clear()
        processed_music_ids.clear()
        processed_hashtag_ids.clear()
        request_map.clear()
        logging.info("Reset processed IDs in tiktok_network_interceptor.")

        # Close the browser
        if browser is not None:
            if hasattr(browser.stop, "__await__"):
                await browser.stop()
            else:
                browser.stop()
            logging.info("User %s: Browser stopped.", user_id)

        # Always attempt to move the temp log file
        try:
            logging.shutdown()
            if testrun_id:
                # Move logs into runs/{test_run_id}/logs
                logs_folder = os.path.join("runs", str(testrun_id), "logs")
                os.makedirs(logs_folder, exist_ok=True)
                dest_log_path = os.path.join(logs_folder, "program.log")
                shutil.move(TEMP_LOG, dest_log_path)
                print(f"All logs for this run moved to {dest_log_path}")
            else:
                # If there's no testrun_id, move logs to a fallback folder within "runs"
                fallback_log_dir = os.path.join("runs", "logs_fallback")
                os.makedirs(fallback_log_dir, exist_ok=True)
                time_str = time.strftime("%Y%m%d_%H%M%S")
                fallback_log_path = os.path.join(
                    fallback_log_dir,
                    f"program_{user_id}_{time_str}.log"
                )
                shutil.move(TEMP_LOG, fallback_log_path)
                print(f"Logs stored in fallback directory => {fallback_log_path}")
        except Exception as move_err:
            print(f"Error moving log file: {move_err}")


if __name__ == "__main__":
    user_ids = list(config.USER_PROFILES.keys())

    if not user_ids:
        logging.error("No user profiles defined in config.py. Exiting.")
    else:
        for uid in user_ids:
            user_config = config.get_user_config(uid)
            logging.info("Starting for USER_ID: %s w/ config: %s", uid, user_config)
            try:
                asyncio.run(main(uid, user_config))
            except Exception as e:
                logging.error("Failed to run main for USER_ID %s: %s", uid, e)