"""
# browse_fyp.py

This module provides functionality for browsing the TikTok "For You Page" (FYP) in an automated fashion,
using browser automation and network interception. It processes video batches, performs user actions
(e.g., watching, liking, following), and **stores all data locally** (JSON files, screenshots, etc.).
We have removed any PostgreSQL database usage and now manage test run IDs by creating numeric folders.

## Features:
- Automatically interact with TikTok's FYP, handle banners, and process video batches.
- Detect and skip livestreams and invalid videos.
- Save video and user-related data into structured local folders.
- Support for user-specific configurations like random actions (e.g., random likes/follows, watch_longer).
- Generate and manage test run directories for storing logs, screenshots, and JSON data.

## Key Functions:
- `handle_floating_banner`: Closes floating banners (e.g., ads) that obstruct the feed.
- `detect_dom_livestream`: Detects if a video element corresponds to a livestream.
- `print_video_details`: Logs detailed information about a specific video.
- `browse_fyp`: The main function for processing the TikTok FYP, interacting with videos, and saving data.

## Usage:
This module requires integration with:
- TikTok network interception tools (e.g., `tiktok_network_interceptor`).
- A browser automation library (`nodriver.core`).
- User-specific configurations for interaction preferences (`user_config`).
- Local "runs/" folder structure for saving test run artifacts.

## Parameters:
### For `browse_fyp`:
- `tab (core.tab)`: The browser tab instance.
- `max_batches (int)`: Maximum number of video batches to process.
- `max_videos (int)`: Maximum number of videos to process.
- `user_id (int)`: The user ID for the session.
- `user_config (dict)`: A dictionary with user-specific preferences, e.g.:
  {
    "RANDOM_POSTS_TO_LIKE": 3,
    "RANDOM_AUTHORS_TO_FOLLOW": 2,
    "RANDOM_VIDEOS_TO_WATCH": 5,
    "HASHTAGS_WATCH_LONGER": ["fyp", "foryoupage", "viral"],
    "HASHTAGS_WATCH_LONGER_COEFFICIENT": 1.2,
    "MAX_WATCHTIME": 120,  # <- clamp watch time
    ...
  }
- `scenario (int)`: The scenario ID for the session.

## Returns:
- `browse_fyp`: Returns the test run ID as a string, or `None` if initialization fails.
"""

import asyncio
import datetime
import json
import logging
import os
import random
import time

from langdetect import LangDetectException, detect

from common.response_utils import dump_response_body_to_json
from nodriver import core
from scraper import tiktok_network_interceptor
from scraper.tiktok_network_interceptor import set_test_run_id
from scraper.video_action_handler import VideoInteractor
from config_loader import load_config


def get_next_test_run_id(scenario: int) -> int:
    """
    Checks the 'runs/scenario_{scenario}' folder for existing numeric subfolders.
    Returns the next integer test run ID (largest existing + 1), or 1 if none exist.
    """
    runs_folder = f"runs/scenario_{scenario}"
    os.makedirs(runs_folder, exist_ok=True)
    
    existing_ids = []
    for name in os.listdir(runs_folder):
        if name.isdigit():
            existing_ids.append(int(name))
    return max(existing_ids) + 1 if existing_ids else 1


async def handle_floating_banner(tab: core.tab) -> None:
    """
    Try to close any floating banner (ad, etc.).
    """
    try:
        script = """
        (function() {
            var closeBtn = document.querySelector('div[class*="DivIconCloseContainer"]');
            if(closeBtn) {
                closeBtn.click();
                return true;
            }
            return false;
        })();
        """
        closed = await tab.evaluate(script)
        if closed:
            logging.info("[handle_floating_banner] Banner closed.")
        else:
            logging.info("[handle_floating_banner] No banner found.")
    except Exception as exc:
        logging.error("[handle_floating_banner] Error => %s", exc)


async def detect_dom_livestream(dom_element: core.element) -> bool:
    """
    Check if this DOM <article> has a "Click to watch LIVE" or similar text
    indicating a livestream, even if skip_this=False in the JSON.
    Returns True if we find that text, otherwise False.
    """
    script = r"""
    (function(){
      if(!this || !this.querySelectorAll) return false;
      var btns = this.querySelectorAll('button');
      for(var i=0; i<btns.length; i++){
        if(btns[i].innerText.includes('LIVE') || btns[i].innerText.includes('Watch LIVE')) {
          return true;
        }
      }
      return false;
    }).call(this);
    """
    try:
        is_live = await dom_element.evaluate(script)
        return bool(is_live)
    except Exception:
        return False


async def print_video_details(details: dict, order: int) -> None:
    """
    Show essential info about the video. 'order' is the global_video_index in browse_fyp.
    """
    logging.info("--------------------------------------------------")
    logging.info(
        "[print_video_details] index=%s, video_id=%s, skip=%s",
        order,
        details["video_id"],
        details["skip_this"],
    )
    logging.info(
        "[print_video_details] author=%s (ID=%s), verified=%s",
        details["author_name"],
        details["author_id"],
        details["author_verified"],
    )
    short_desc = details["description"][:60] if details["description"] else ""
    logging.info(
        "[print_video_details] duration=%ss, desc=%s ...",
        details["duration"],
        short_desc,
    )
    logging.info("[print_video_details] hashtags=%s", details["hashtags"])
    logging.info("[print_video_details] fullurl=%s", details["fullurl"])
    logging.info("--------------------------------------------------")
    await asyncio.sleep(0.2)


async def browse_fyp(
    tab: core.tab,
    max_batches: int,
    max_videos: int,
    user_id: int,
    user_config: dict,
    scenario: float,
) -> str or None:
    """
    Main function for processing TikTok's FYP:
      1) We fetch "batches" of video details from a global queue (video_batches_queue).
      2) For each item, we store a screenshot locally. If skip_this=True or it's a livestream/ad,
         we store that screenshot in a 'streams_ads' folder.
      3) We watch videos or perform random actions (like/follow/watch_longer) according to user_config.
         We ensure watch time never exceeds user_config["MAX_WATCHTIME"] (default 120s).
      4) We store local artifacts (screenshots, request/response JSON, interactions) in 'runs/{test_run_id}/'.

    Additionally, if we randomly selected a video to "like" but that video is
    marked skippable (ad or livestream), we skip that post and immediately attempt
    to like the next post instead.

    Returns:
      - The test run ID (string) if everything initializes successfully, or
      - None if the run cannot be started (e.g., can't find "For You" button).
    """
    await tab

    # Config load
    config = load_config()

    # Get different max watch times from config
    max_watchtime = 120  # Default base watch time

    # If MAX_WATCHTIME is specified in config, use that instead of default
    if hasattr(config, 'MAX_WATCHTIME'):
        max_watchtime = config.MAX_WATCHTIME

    # Optional extended watch times - For scenarios with watch_longer or random watch
    hashtags_max_watchtime = max_watchtime  # Default to regular max_watchtime
    random_max_watchtime = max_watchtime    # Default to regular max_watchtime

    # If special watch times are specified in config, use those
    if hasattr(config, 'HASHTAGS_WATCH_LONGER_MAXWATCHTIME'):
        hashtags_max_watchtime = config.HASHTAGS_WATCH_LONGER_MAXWATCHTIME
    if hasattr(config, 'RANDOM_WATCH_MAXWATCHTIME'):
        random_max_watchtime = config.RANDOM_WATCH_MAXWATCHTIME

    logging.info(
        "[browse_fyp] Watch time limits: normal=%ss, hashtag videos=%ss, random watch=%ss",
        max_watchtime,
        hashtags_max_watchtime,
        random_max_watchtime
    )

    # 1) Generate a new test run ID
    test_run_number = get_next_test_run_id(scenario)
    testrunid = str(test_run_number)

    logging.info("[browse_fyp] Start => scenario=%s, user_id=%s, testRunID=%s",
                scenario, user_id, testrunid)
    logging.info("[browse_fyp] user_config => %s", user_config if user_config else "-1")

    # 2) Create run folders
    set_test_run_id(testrunid, scenario)
    run_folder = f"runs/scenario_{scenario}/{testrunid}"
    requests_folder = os.path.join(run_folder, "requests")
    responses_folder = os.path.join(run_folder, "responses")
    screenshots_folder = os.path.join(run_folder, "screenshots")
    streams_ads_folder = os.path.join(run_folder, "streams_ads")
    user_config_folder = os.path.join(run_folder, "user_config")
    interactions_folder = os.path.join(run_folder, "interactions")

    os.makedirs(user_config_folder, exist_ok=True)
    os.makedirs(interactions_folder, exist_ok=True)

    # 3) Write out the config data to config.json
    config_data = {
        "SCENARIO": config.SCENARIO,
        "USE_PROXY": config.USE_PROXY,
        "USE_LOGIN": config.USE_LOGIN,
        "REUSE_COOKIES": config.REUSE_COOKIES,
        "COUNTRY": config.COUNTRY,
        "TARGET_ENDPOINT": config.TARGET_ENDPOINT,
        "NUM_BATCHES": config.NUM_BATCHES,
        "MAX_VIDEOS": config.MAX_VIDEOS,
        "PROXYHOST": config.PROXYHOST,
        "PROXYPORT": config.PROXYPORT,
        "PROXYUSERNAME": config.PROXYUSERNAME,
        "PROXYPASSWORD": config.PROXYPASSWORD,
        "PROXY": config.PROXY,
        "TIKTOK_EMAIL": config.TIKTOK_EMAIL,
        "TIKTOK_PASSWORD": config.TIKTOK_PASSWORD,
        "USER_PROFILES": config.USER_PROFILES,
        "MAX_WATCHTIME": max_watchtime,
    }

    user_config_path = os.path.join(user_config_folder, "config.json")
    try:
        with open(user_config_path, "w", encoding="utf-8") as fh:
            json.dump(config_data, fh, indent=2)
        logging.info("[browse_fyp] Stored run config => %s", user_config_path)
    except Exception as exc:
        logging.error("[browse_fyp] Failed to store user_config => %s", exc)

    # Helper to store interactions (like/follow/random_watch/watch_longer) as JSON
    def store_interaction(action_type: str, video_id: str):
        """
        Store a short JSON record in runs/{testrunid}/interactions/.
        """
        record = {
            "action_type": action_type,
            "video_id": video_id,
            "user_id": user_id,
            "timestamp": time.time(),
            "test_run_id": testrunid,
        }
        filename = f"{action_type}_{video_id}_{time.strftime('%Y%m%d-%H%M%S')}.json"
        path = os.path.join(interactions_folder, filename)
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(record, fh, indent=2)
            logging.info(
                "[store_interaction] Action=%s, video_id=%s => %s",
                action_type,
                video_id,
                path,
            )
        except Exception as exc:
            logging.error("[store_interaction] Failed to store => %s", exc)

    try:
        # Attempt to click "For You" on main page
        if config.USE_PROXY:
            # Sometimes needs more time if a proxy is used
            await asyncio.sleep(25)
        else:
            await asyncio.sleep(5)
        logging.info("[browse_fyp] Looking for 'For You' button on main page.")
        fyp_button = await tab.find("For You", best_match=True, timeout=120)
        if fyp_button:
            logging.info("[browse_fyp] Found 'For You' => clicking now.")
            if config.USE_PROXY:
                await asyncio.sleep(15)
            else:
                await asyncio.sleep(3)
            await fyp_button.click()
            await asyncio.sleep(5)
        else:
            logging.info("[browse_fyp] Could not find 'For You' => cannot proceed.")
            return None

        # Close any floating banner
        await handle_floating_banner(tab)
        if config.USE_PROXY:
            await asyncio.sleep(5)
        else:
            await asyncio.sleep(1)

        global_video_index = 0
        batch_count = 0
        total_videos_processed = 0

        # Prepare random sets if logged in
        if config.USE_LOGIN and user_config:
            rand_likes = min(user_config.get("RANDOM_POSTS_TO_LIKE", 0), max_videos)
            rand_follows = min(user_config.get("RANDOM_AUTHORS_TO_FOLLOW", 0), max_videos)
            rand_watches = min(user_config.get("RANDOM_VIDEOS_TO_WATCH", 0), max_videos)

            indices_to_random_like = random.sample(range(max_videos), rand_likes)
            indices_to_random_follow = random.sample(range(max_videos), rand_follows)
            indices_to_random_watch = random.sample(range(max_videos), rand_watches)

            logging.info("[browse_fyp] random LIKE => %s", indices_to_random_like)
            logging.info("[browse_fyp] random FOLLOW => %s", indices_to_random_follow)
            logging.info("[browse_fyp] random WATCH => %s", indices_to_random_watch)
        else:
            indices_to_random_like = []
            indices_to_random_follow = []
            indices_to_random_watch = []

        # Main loop
        while batch_count < max_batches and total_videos_processed < max_videos:
            try:
                logging.info("[browse_fyp] Waiting up to 60s for next video batch...")
                batch_data = await asyncio.wait_for(
                    tiktok_network_interceptor.video_batches_queue.get(), timeout=60
                )
            except asyncio.TimeoutError:
                logging.info("[browse_fyp] Timed out => no new batch => stopping.")
                break

            video_batch = batch_data["video_details_list"]
            request_data = batch_data["combined_data"]["request"]
            response_data = batch_data["combined_data"]["response"]
            decoded_str = batch_data["json_data"]

            logging.info("[browse_fyp] Received a batch => %s items.", len(video_batch))
            if not video_batch:
                logging.info("[browse_fyp] Batch is empty => continuing.")
                continue

            batch_count += 1
            logging.info("[browse_fyp] Batch #%s => storing local request/response JSON", batch_count)

            ts_now = time.strftime("%Y%m%d-%H%M%S")

            # Store request
            request_filename = f"{user_id}_{ts_now}.json"
            request_path = os.path.join(requests_folder, request_filename)
            with open(request_path, "w", encoding="utf-8") as fh:
                json.dump(request_data, fh, indent=2)
            logging.info("[browse_fyp] Stored batch request JSON => %s", request_path)

            # Store response
            response_filename = f"{user_id}_{ts_now}.json"
            response_path = os.path.join(responses_folder, response_filename)
            dump_response_body_to_json(decoded_str, response_path)
            logging.info("[browse_fyp] Stored batch response JSON => %s", response_path)

            i = 0
            while i < len(video_batch):
                if total_videos_processed >= max_videos:
                    logging.info("[browse_fyp] Reached max_videos=%s => done.", max_videos)
                    return testrunid

                details = video_batch[i]
                logging.info("[browse_fyp] Processing item i=%s, global_index=%s", i, global_video_index)
                await print_video_details(details, global_video_index)

                # Attempt to select article
                await tab
                article_selector = f"article[data-scroll-index='{global_video_index}']"
                dom_article = await tab.select(article_selector, timeout=60)
                if not dom_article:
                    logging.warning(
                        "[browse_fyp] No <article> => index=%s => feed might have ended.",
                        global_video_index,
                    )
                    break

                # Screenshot
                await dom_article.scroll_into_view()
                screenshot_path = os.path.join(screenshots_folder, f"{global_video_index}.jpeg")
                await asyncio.sleep(0.5)
                await tab.save_screenshot(filename=screenshot_path, format="jpeg", full_page=False)
                logging.info("[browse_fyp] Screenshot => %s", screenshot_path)

                # Skip logic
                while True:
                    if details.get("skip_this", False):
                        logging.info("[browse_fyp] skip_this=True => skipping item.")
                        skip_path = os.path.join(streams_ads_folder, f"{global_video_index}.jpeg")
                        await tab.save_screenshot(filename=skip_path, format="jpeg", full_page=False)
                        logging.info("[browse_fyp] skip screenshot => %s", skip_path)

                        global_video_index += 1
                        i += 1
                        if i >= len(video_batch):
                            break
                        details = video_batch[i]
                        logging.info("[browse_fyp] Next => i=%s, global_index=%s", i, global_video_index)

                        article_selector = f"article[data-scroll-index='{global_video_index}']"
                        dom_article = await tab.select(article_selector, timeout=60)
                        if not dom_article:
                            logging.warning(
                                "[browse_fyp] No <article> => index=%s after skip.", global_video_index
                            )
                            break

                        await print_video_details(details, global_video_index)
                        await dom_article.scroll_into_view()
                        screenshot_path = os.path.join(screenshots_folder, f"{global_video_index}.jpeg")
                        await tab.save_screenshot(filename=screenshot_path, format="jpeg", full_page=False)
                        logging.info("[browse_fyp] Screenshot => %s", screenshot_path)
                        continue

                    is_live = await detect_dom_livestream(dom_article)
                    if is_live:
                        logging.info("[browse_fyp] DOM-livestream => skipping item.")
                        skip_path = os.path.join(streams_ads_folder, f"{global_video_index}.jpeg")
                        await tab.save_screenshot(filename=skip_path, format="jpeg", full_page=False)
                        logging.info("[browse_fyp] skip screenshot => %s", skip_path)

                        global_video_index += 1
                        i += 1
                        if i >= len(video_batch):
                            break
                        details = video_batch[i]
                        logging.info("[browse_fyp] Next => i=%s, global_index=%s", i, global_video_index)

                        article_selector = f"article[data-scroll-index='{global_video_index}']"
                        dom_article = await tab.select(article_selector, timeout=60)
                        if not dom_article:
                            logging.warning(
                                "[browse_fyp] No <article> => index=%s after skip.", global_video_index
                            )
                            break

                        await print_video_details(details, global_video_index)
                        await dom_article.scroll_into_view()
                        screenshot_path = os.path.join(screenshots_folder, f"{global_video_index}.jpeg")
                        await tab.save_screenshot(filename=screenshot_path, format="jpeg", full_page=False)
                        logging.info("[browse_fyp] Screenshot => %s", screenshot_path)
                        continue

                    # Not skipping => break
                    break

                if i >= len(video_batch):
                    break

                logging.info("[browse_fyp] Valid => global_index=%s", global_video_index)

                # If we want to do user actions:
                if config.USE_LOGIN and user_config:
                    v_interactor = VideoInteractor(
                        tab=tab,
                        video_element=dom_article,
                        video_details=details,
                        video_index=global_video_index,
                        user_config=user_config,
                        scenario=scenario,
                    )


                    await v_interactor.handle_video_actions()


                    do_random_like = (global_video_index in indices_to_random_like)
                    do_random_follow = (global_video_index in indices_to_random_follow)
                    do_random_watch = (global_video_index in indices_to_random_watch)

                    # Identify hashtags, watch settings, etc.
                    hashtags_lower = [h.lower() for h in details.get("hashtags", [])]
                    watch_longer_tags = user_config.get("HASHTAGS_WATCH_LONGER", [])
                    has_watch_longer_tags = any(tag in hashtags_lower for tag in watch_longer_tags)

                    if has_watch_longer_tags:
                        watch_coeff = user_config.get("HASHTAGS_WATCH_LONGER_COEFFICIENT", 1.0)
                    else:
                        watch_coeff = user_config.get("WATCH_COEFFICIENT_NO_HASHTAGS", 1.0)

                    def clamp_watch_coefficient(cf: float, has_watch_longer_tags: bool, is_random_watch: bool = False) -> float:
                        """
                        If cf * video_duration > max_watchtime => clamp.
                        Uses different max watch times based on video type:
                        - hashtags_max_watchtime for videos with watch longer tags
                        - random_max_watchtime for randomly selected videos
                        - max_watchtime for regular videos
                        """
                        dur = details.get("duration", 0.0)
                        if dur <= 0:
                            return cf

                        watch_secs = cf * dur

                        # Determine which max watch time to use
                        if is_random_watch:
                            current_max = random_max_watchtime
                            watch_type = "random"
                        elif has_watch_longer_tags:
                            current_max = hashtags_max_watchtime
                            watch_type = "hashtag"
                        else:
                            current_max = max_watchtime
                            watch_type = "normal"

                        if watch_secs > current_max:
                            new_cf = current_max / dur
                            logging.info(
                                "[browse_fyp] Clamping %s watch from %.1f to max %.1f s => new coeff=%.2f",
                                watch_type,
                                watch_secs,
                                current_max,
                                new_cf,
                            )
                            return new_cf
                        return cf

                    # Clamp the coefficient based on whether this video has watch longer tags
                    watch_coeff = clamp_watch_coefficient(watch_coeff, has_watch_longer_tags, is_random_watch=do_random_watch)


                    #if we want to LIKE but this item is skip/ad, increment index
                    # until we find a valid item to like.
                    # We'll do this in a small helper function
                    def find_next_non_skippable_for_like():
                        nonlocal i, global_video_index, details, dom_article
                        while True:
                            if i >= len(video_batch):
                                return False
                            if details.get("skip_this", False) or details.get("isAd", False):
                                # Move to next item
                                logging.info(
                                    "[browse_fyp] Wanted to like index=%s but skip/ad => incrementing to next...",
                                    global_video_index
                                )
                                global_video_index += 1
                                i += 1
                                if i < len(video_batch):
                                    details = video_batch[i]
                                else:
                                    return False
                            else:
                                # If not skip/ad => done
                                return True
                            # Re-select new article
                            selector = f"article[data-scroll-index='{global_video_index}']"
                            new_article = None
                            try:
                                new_article = asyncio.run_coroutine_threadsafe(
                                    tab.select(selector, timeout=60),
                                    asyncio.get_event_loop()
                                ).result()
                            except:
                                pass
                            if not new_article:
                                logging.warning(
                                    "[browse_fyp] No <article> => index=%s after skipping => feed ended?",
                                    global_video_index
                                )
                                return False
                            dom_article = new_article


                    # DO RANDOM LIKE
                    if do_random_like:
                        # Attempt to skip ad/live items until we find one to like
                        can_like = find_next_non_skippable_for_like()
                        if not can_like:
                            # No valid item to like => break out
                            logging.info("[browse_fyp] No valid item found to like => stopping like attempt.")
                        else:
                            logging.info("[browse_fyp] random LIKE => index=%s", global_video_index)
                            await v_interactor.like()
                            store_interaction("like", details["video_id"])

                    # DO FOLLOW
                    if do_random_follow:
                        logging.info("[browse_fyp] random FOLLOW => index=%s", global_video_index)
                        await v_interactor.follow_user()
                        store_interaction("follow", details["video_id"])

                    # DO WATCH
                    if do_random_watch:
                        logging.info("[browse_fyp] random PARTIAL watch => index=%s", global_video_index)
                        part_cf = user_config.get("RANDOM_WATCH_COEFFICIENT", 1.0)
                        part_cf = clamp_watch_coefficient(part_cf, has_watch_longer_tags, is_random_watch=True)
                        await v_interactor.watch_video(coefficient=part_cf)
                        store_interaction("random_watch", details["video_id"])
                    else:
                        watch_coeff = clamp_watch_coefficient(watch_coeff, has_watch_longer_tags, is_random_watch=False)
                        logging.info("[browse_fyp] normal watch => coeff=%s, index=%s", watch_coeff, global_video_index)
                        await v_interactor.watch_video(coefficient=watch_coeff)
                        if has_watch_longer_tags and watch_coeff > 1.0:
                            store_interaction("watch_longer", details["video_id"])

                    await asyncio.sleep(1)
                else:
                    logging.info("[browse_fyp] Not logged in => skip watch/like/follow logic.")

                # Language detection
                desc_str = details.get("description") or ""
                try:
                    lang_detected = detect(desc_str)
                    lang_label = lang_detected.upper()
                except LangDetectException:
                    lang_detected = "unknown"
                    lang_label = "UNKNOWN"

                global_video_index += 1
                total_videos_processed += 1
                i += 1

            logging.info("[browse_fyp] Finished batch=%s, now scrolling => index=%s", batch_count, global_video_index)

            scroll_script = f"""
            (function() {{
                var nextArt = document.querySelector('article[data-scroll-index="{global_video_index}"]');
                if(nextArt) {{
                    nextArt.scrollIntoView();
                    return true;
                }}
                return false;
            }})();
            """
            scrolled = await tab.evaluate(scroll_script)
            if scrolled:
                logging.info("[browse_fyp] Scrolled to data-scroll-index=%s, waiting 5s...", global_video_index)
            else:
                logging.info("[browse_fyp] No article at index=%s => feed ended.", global_video_index)
            await asyncio.sleep(5)

        logging.info(
            "[browse_fyp] Done => Batches=%s/%s, Videos=%s/%s.",
            batch_count,
            max_batches,
            total_videos_processed,
            max_videos,
        )

    except Exception as exc:
        logging.error("[browse_fyp] Exception => %s", exc)

    # Final
    logging.info("[browse_fyp] Test run %s ended successfully (no DB).", testrunid)
    return testrunid