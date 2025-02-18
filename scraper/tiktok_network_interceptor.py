"""
TikTok Network Interceptor

This module provides functionality for intercepting network requests and responses 
from TikTok's API. It handles data collection, processing, and storage of request 
and response payloads. It also manages a test run ID system for organized data 
storage.

Main Features:
- Set up directories for test runs.
- Intercept and handle requests and responses.
- Process and store video data in JSON files.
- Helper functions for queue management and URL parsing.

Modules:
- `set_test_run_id`: Initializes a test run directory structure.
- `set_video_batches_queue`: Assigns a new queue for video batches.
- Handlers for `RequestWillBeSent`, `ResponseReceived`, and `LoadingFinished`.
- Helper functions for URL parsing and storing requests/responses.

Dependencies:
- `nodriver.core` for tab manipulation.
- `common.response_utils` for data processing.
"""

import asyncio
import base64
import json
import logging
import os
import time
import uuid
from urllib.parse import parse_qs, urlparse
from pathlib import Path

from common.response_utils import clean_text, decode_response_body, decompress_response_body
from nodriver import cdp, core
from config_loader import load_config

# ------------------------------------------------------------------------------------
# TEST RUN ID + DIRECTORY STRUCTURE
# ------------------------------------------------------------------------------------
test_run_id = None
current_scenario = None
config = None


def set_test_run_id(run_id: str, scenario: float):
    """
    Call this once at the start of a test run.
    Creates subdirectories under runs/scenario_{scenario}/ for the current run.
    """
    global test_run_id, current_scenario, config
    test_run_id = run_id
    current_scenario = scenario
    config = load_config()

    # Create the master runs folder (if not present)
    os.makedirs("runs", exist_ok=True)
    # Use string formatting to avoid decimal point in folder name
    scenario_dir = f"runs/scenario_{scenario:.1f}"  # Use the passed scenario ID
    os.makedirs(scenario_dir, exist_ok=True)

    # Create subfolders for this specific test_run_id
    run_dir = f"{scenario_dir}/{test_run_id}"
    os.makedirs(run_dir, exist_ok=True)
    os.makedirs(f"{run_dir}/screenshots", exist_ok=True)
    os.makedirs(f"{run_dir}/streams_ads", exist_ok=True)
    os.makedirs(f"{run_dir}/invalid_jsons", exist_ok=True)
    os.makedirs(f"{run_dir}/requests", exist_ok=True)
    os.makedirs(f"{run_dir}/responses", exist_ok=True)

    logging.info(
        "[set_test_run_id] New test run folder structure created at %s",
        run_dir,
    )


# ------------------------------------------------------------------------------------
# GLOBALS & QUEUE
# ------------------------------------------------------------------------------------

request_map = {}
video_batches_queue = None  # Set by set_video_batches_queue() in main.py

processed_request_ids = set()
pending_request_ids = set()

processed_video_ids = set()
processed_author_ids = set()
processed_music_ids = set()
processed_hashtag_ids = set()

generated_json_files = []

followed_users = set()


# ------------------------------------------------------------------------------------
# QUEUE SETTER
# ------------------------------------------------------------------------------------

def set_video_batches_queue(q: asyncio.Queue):
    """
    Called by main.py to provide a fresh queue each time.
    This ensures leftover items from a prior user_id don't persist.
    """
    global video_batches_queue
    video_batches_queue = q
    logging.info("[set_video_batches_queue] A new queue has been assigned.")


# ------------------------------------------------------------------------------------
# REQUEST & RESPONSE HANDLERS
# ------------------------------------------------------------------------------------

async def request_will_be_sent_handler(
    event: cdp.network.RequestWillBeSent, connection: core.tab
) -> None:
    """
    Handle request events.
    """
    global config
    if not config:
        config = load_config()

    if event.request.url.startswith(config.TARGET_ENDPOINT):
        logging.info(
            "[request_will_be_sent_handler] Detected request to TARGET_ENDPOINT. request_id=%s",
            event.request_id,
        )
        asyncio.create_task(handle_request(event))


async def handle_request(event: cdp.network.RequestWillBeSent) -> None:
    """
    Store request details for future debugging or correlation with the response.
    """
    try:
        url_info = parse_url_to_json(event.request.url)
        req_id = event.request_id
        request_headers = dict(event.request.headers)
        request_method = event.request.method

        request_data = {
            "url": url_info,
            "request_id": req_id,
            "headers": request_headers,
            "method": request_method,
            "timestamp": time.time(),
        }
        request_map[req_id] = request_data
        logging.info("[handle_request] Stored details for request_id=%s", req_id)
    except Exception as exc:
        logging.error("[handle_request] Error storing request data => %s", exc)


async def response_received_handler(
    event: cdp.network.ResponseReceived, connection: core.tab
) -> None:
    """
    Handle response events.
    """
    global config
    if not config:
        config = load_config()

    if event.response.url.startswith(config.TARGET_ENDPOINT):
        req_id = event.request_id
        if req_id in processed_request_ids:
            logging.info(
                "[response_received_handler] request_id=%s already processed; skipping.",
                req_id,
            )
            return

        processed_request_ids.add(req_id)
        pending_request_ids.add(req_id)
        logging.info(
            "[response_received_handler] Enqueued request_id=%s in pending_request_ids",
            req_id,
        )


async def loading_finished_handler(
    event: cdp.network.LoadingFinished, connection: core.tab
) -> None:
    """
    Once the loading is fully finished for a request, we can parse the body reliably.
    If request_id is in pending_request_ids, call handle_response.
    """
    await connection
    req_id = event.request_id
    if req_id in pending_request_ids:
        logging.info(
            "[loading_finished_handler] request_id=%s => handle_response now.", req_id
        )
        pending_request_ids.remove(req_id)
        asyncio.create_task(handle_response(req_id, connection))


# ------------------------------------------------------------------------------------
# HELPER FUNCTIONS TO PRINT QUEUE & BATCH
# ------------------------------------------------------------------------------------

def _print_new_json_title():
    """
    Replaces print with logging.info to indicate a new JSON batch.
    """
    logging.info("\nNEW JSON...")

def _print_current_queue_title():
    """
    Replaces print with logging.info to indicate the current queue listing.
    """
    logging.info("\nCURRENT QUEUE:")

def _print_item_with_info(index: int, details: dict):
    """
    Replaces print with logging.info. 
    Example of output: 
        '1. video [author=..., desc=...]'
    or
        '1. livestream [author=..., desc=...]'
    """
    item_type = "livestream" if details.get("skip_this", False) else "video"

    desc_snippet = details.get("description", "")
    if len(desc_snippet) > 30:
        desc_snippet = desc_snippet[:30] + "..."

    author_name = details.get("author_name", "Unknown Author")
    logging.info("%s. %s [author=%s, desc=%s]", index, item_type, author_name, desc_snippet)


def _print_batch_items(video_details_list):
    """
    Calls _print_new_json_title, then logs each item in video_details_list.
    """
    _print_new_json_title()
    for idx, details in enumerate(video_details_list, start=1):
        _print_item_with_info(idx, details)


def _print_current_queue_items():
    """
    Logs the entire queue in "CURRENT QUEUE:" format.
    We use video_batches_queue._queue (an internal detail).
    """
    if video_batches_queue is None:
        logging.info("Queue is not initialized yet.")
        return

    queue_items = list(video_batches_queue._queue)

    _print_current_queue_title()
    if not queue_items:
        logging.info("No items in queue.")
        return

    current_index = 1
    for batch_data in queue_items:
        video_list = batch_data.get("video_details_list", [])
        for details in video_list:
            _print_item_with_info(current_index, details)
            current_index += 1


# ------------------------------------------------------------------------------------
# HANDLE RESPONSE
# ------------------------------------------------------------------------------------

async def handle_response(request_id: str, connection: core.tab) -> None:
    """
    Retrieve and parse the response body from request_id, once fully loaded.
    Mark skip_this=True if:
      - duration=0.0
      - containerType=2 (livestream)
      - "LIVE now" is found
      - isAd == True (advertisement)
    """
    await connection
    logging.info("[handle_response] Invoked => request_id=%s", request_id)

    body = None
    is_base64_encoded = False
    attempt_failed = False

    # Attempt up to 5 times
    for attempt in range(5):
        try:
            resp = await connection.send(
                cdp.network.get_response_body(request_id=request_id)
            )
            if resp:
                body, is_base64_encoded = resp
                break
            else:
                if attempt == 0:
                    logging.warning(
                        "[handle_response] get_response_body() returned None => request_id=%s, retrying...",
                        request_id,
                    )
                    await asyncio.sleep(2)
                else:
                    attempt_failed = True
        except asyncio.CancelledError:
            logging.info("[handle_response] Cancelled => request_id=%s", request_id)
            return
        except Exception as exc:
            logging.error("[handle_response] Error => request_id=%s: %s", request_id, exc)
            attempt_failed = True
            break

    if attempt_failed:
        logging.error(
            "[handle_response] get_response_body() returned None (5th attempt) => request_id=%s",
            request_id,
        )
        ts_now = time.strftime("%Y%m%d-%H%M%S")
        invalid_json = {
            "request_id": request_id,
            "request_data": request_map.get(request_id, {}),
            "timestamp": time.time(),
            "message": "Could not retrieve response body (None) after a fifth attempt.",
        }
        if test_run_id:
            invalid_fname = f"runs/scenario_{current_scenario:.1f}/{test_run_id}/invalid_jsons/invalid_{ts_now}_{request_id}.json"
        else:
            os.makedirs(f"runs/scenario_{current_scenario:.1f}", exist_ok=True)
            invalid_fname = f"runs/scenario_{current_scenario:.1f}/unknown_run_invalid_{ts_now}_{request_id}.json"

        with open(invalid_fname, "w", encoding="utf-8") as fh:
            json.dump(invalid_json, fh, indent=2)
        logging.info("[handle_response] Saved invalid JSON => %s", invalid_fname)
        return

    if not body:
        logging.warning(
            "[handle_response] Body is still None => request_id=%s. Skipping parse.",
            request_id,
        )
        return

    try:
        # Decompress + decode if needed
        if is_base64_encoded:
            body = base64.b64decode(body)

        body = decompress_response_body(body, "utf-8")
        decoded_str = decode_response_body(body)
        data = json.loads(decoded_str)

        # Combined data (optional)
        req_data = request_map.get(request_id, {})
        combined_data = {
            "request": req_data,
            "response": data,
            "request_id": request_id,
            "timestamp": time.time(),
        }

        # If there's no itemList => no videos
        if "itemList" not in data:
            logging.info(
                "[handle_response] 'itemList' missing => no new videos => request_id=%s",
                request_id,
            )
            return

        videos = data["itemList"]
        logging.info(
            "[handle_response] request_id=%s => Found %s items in itemList.",
            request_id,
            len(videos),
        )

        video_details_list = []

        for vid_obj in videos:
            container_type = vid_obj.get("containerType", None)
            live_info = vid_obj.get("liveRoomInfo", {})

            raw_id = vid_obj.get("id", "").strip()
            if not raw_id:
                if container_type == 2 and "roomID" in live_info:
                    raw_id = f"livestream_{live_info['roomID']}"
                else:
                    raw_id = f"unknown_{uuid.uuid4()}"

            vid_id = raw_id
            if vid_id in processed_video_ids:
                logging.info(
                    "[handle_response] Video ID=%s already processed => skipping.",
                    vid_id,
                )
                continue

            processed_video_ids.add(vid_id)
            skip_it = False

            # If containerType=2 => likely livestream => skip
            if container_type == 2:
                skip_it = True
                logging.info(
                    "[handle_response] containerType=2 => skip_it=True (livestream/container)"
                )

            # If there's a liveRoomInfo => also livestream => skip
            if "liveRoomInfo" in vid_obj:
                skip_it = True
                logging.info(
                    "[handle_response] Found liveRoomInfo => skip_it=True (livestream)"
                )
                if "fypRoomTag" in live_info:
                    tags = live_info["fypRoomTag"].get("tag", [])
                    for tag in tags:
                        if tag.get("content") == "LIVE now":
                            logging.info(
                                "[handle_response] Found 'LIVE now' tag in liveRoomInfo"
                            )

            # If no 'video' key => also skip
            video_stats = vid_obj.get("video", {})
            if not video_stats:
                skip_it = True
                logging.info(
                    "[handle_response] No 'video' key => skip_it=True (likely livestream/container)"
                )

            # If duration=0.0 => skip
            raw_duration = 0.0
            if video_stats:
                try:
                    raw_duration = float(video_stats.get("duration", 0))
                except (TypeError, ValueError):
                    raw_duration = 0.0
                if raw_duration == 0.0:
                    skip_it = True
                    logging.info("[handle_response] duration=0.0 => skip_it=True")

            # If isAd => skip
            is_ad = vid_obj.get("isAd", False)
            if is_ad:
                skip_it = True
                logging.info("[handle_response] isAd=True => skip_it=True (advertisement)")
            logging.info(
                "[handle_response] Video => id=%s, containerType=%s, duration=%s, "
                "live_info_present=%s, isAd=%s => skip_this=%s",
                vid_id,
                container_type,
                raw_duration,
                "liveRoomInfo" in vid_obj,
                is_ad,
                skip_it,
            )

            # Build the final details dict
            author = vid_obj.get("author", {})
            stats = vid_obj.get("stats", {})
            music = vid_obj.get("music", {})
            contents = vid_obj.get("contents", [{}])
            text_extras = contents[0].get("textExtra", []) if contents else []
            author_stats = vid_obj.get("authorStats", {})
            challenges = vid_obj.get("challenges", [])

            play_count = stats.get("playCount", 0)
            digg_count = stats.get("diggCount", 0)
            share_count = stats.get("shareCount", 0)
            comment_count = stats.get("commentCount", 0)
            collect_count = stats.get("collectCount", 0)
            repost_count = vid_obj.get("statsV2", {}).get("repostCount", 0)
            loudness = video_stats.get("volumeInfo", {}).get("Loudness", "N/A")

            author_id = author.get("id", "Unknown Author")
            author_name = clean_text(author.get("nickname", "Unknown Author Name"))
            author_unique_id = author.get("uniqueId", "Unknown")
            author_sec_uid = author.get("secUid", "Unknown")
            author_verified = author.get("verified", False)

            author_following_count = author_stats.get("followingCount", 0)
            author_follower_count = author_stats.get("followerCount", 0)
            author_heart_count = author_stats.get("heartCount", 0)
            author_video_count = author_stats.get("videoCount", 0)
            author_digg_count = author_stats.get("diggCount", 0)

            music_name = clean_text(music.get("title", "Unknown Music Title"))
            music_id = music.get("id", "Unknown Music ID")
            music_author = clean_text(music.get("authorName", "Unknown Music Author"))
            music_album = clean_text(music.get("album", "Unknown Album"))

            hashtags = []
            for t_ex in text_extras:
                if t_ex.get("type") == 1:
                    hashtags.append(clean_text(t_ex.get("hashtagName", "")))

            hashtag_info = []
            for ch in challenges:
                ch_id = ch.get("id", "Unknown")
                ch_title = clean_text(ch.get("title", ""))
                ch_desc = clean_text(ch.get("desc", ""))
                hashtag_info.append(
                    {
                        "id": ch_id,
                        "title": ch_title,
                        "desc": ch_desc,
                    }
                )

            desc_text = clean_text(vid_obj.get("desc", ""))
            if author_unique_id != "Unknown" and vid_id != "Unknown ID":
                fullurl = f"https://www.tiktok.com/@{author_unique_id}/video/{vid_id}"
            else:
                fullurl = "N/A"
                logging.warning(
                    "[handle_response] Could not build fullurl => video_id=%s", vid_id
                )

            details = {
                "video_id": vid_id,
                "author_id": author_id,
                "author_name": author_name,
                "author_bio": clean_text(author.get("signature", "No bio")),
                "author_unique_id": author_unique_id,
                "author_sec_uid": author_sec_uid,
                "author_verified": author_verified,
                "author_following_count": author_following_count,
                "author_follower_count": author_follower_count,
                "author_heart_count": author_heart_count,
                "author_video_count": author_video_count,
                "author_digg_count": author_digg_count,
                "play_count": play_count,
                "digg_count": digg_count,
                "share_count": share_count,
                "comment_count": comment_count,
                "collect_count": collect_count,
                "repost_count": repost_count,
                "loudness": loudness,
                "duration": raw_duration,
                "description": desc_text,
                "music_name": music_name,
                "music_id": music_id,
                "music_author": music_author,
                "music_album": music_album,
                "hashtags": hashtags,
                "hashtag_info": hashtag_info,
                "fullurl": fullurl,
                "isAd": is_ad,
                "skip_this": skip_it,
            }
            video_details_list.append(details)

        # Log them
        _print_batch_items(video_details_list)

        if video_details_list:
            if video_batches_queue:
                batch_payload = {
                    "video_details_list": video_details_list,
                    "json_data": decoded_str,
                    "combined_data": combined_data,
                }
                logging.info(
                    "[handle_response] Enqueuing %s items => video_batches_queue.",
                    len(video_details_list),
                )
                await video_batches_queue.put(batch_payload)
                _print_current_queue_items()
            else:
                logging.error(
                    "[handle_response] video_batches_queue is None => cannot enqueue."
                )
        else:
            logging.info("[handle_response] No new or unprocessed items found in response.")

    except asyncio.CancelledError:
        logging.info("[handle_response] Cancelled => request_id=%s", request_id)
    except Exception as exc:
        logging.error("[handle_response] Error => request_id=%s: %s", request_id, exc)


# ------------------------------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------------------------------

def parse_url_to_json(url: str) -> dict:
    """
    Convert a URL + query string into a structured dict:
    {
        "url": url,
        "target_endpoint": ...,
        "params": {...}
    }
    """
    parsed = urlparse(url)
    url_dict = {
        "url": url,
        "target_endpoint": f"{parsed.scheme}://{parsed.netloc}{parsed.path}",
        "params": {},
    }
    qvals = parse_qs(parsed.query)
    for k, v in qvals.items():
        url_dict["params"][k] = v[0] if len(v) == 1 else v
    return url_dict


async def store_request(request_data: dict) -> None:
    """Store request data in the scenario-specific folder"""
    global test_run_id, current_scenario

    if test_run_id and current_scenario:
        path_req = f"runs/scenario_{current_scenario:.1f}/{test_run_id}/requests/requests.json"
    else:
        os.makedirs(f"runs/scenario_{current_scenario:.1f}", exist_ok=True)
        path_req = f"runs/scenario_{current_scenario:.1f}/unknown_run_requests.json"

    try:
        existing = []
        if os.path.exists(path_req):
            with open(path_req, "r", encoding="utf-8") as fh:
                try:
                    existing = json.load(fh)
                    if not isinstance(existing, list):
                        existing = []
                except json.JSONDecodeError:
                    existing = []

        existing.append(request_data)
        with open(path_req, "w", encoding="utf-8") as fh:
            json.dump(existing, fh, indent=2)

        logging.info("[store_request] Appended request/response => %s", path_req)

    except Exception as exc:
        logging.error("[store_request] Failed to store => %s", exc)


async def store_response(response_data: dict) -> None:
    """Store response data in the scenario-specific folder"""
    global test_run_id, current_scenario

    if test_run_id and current_scenario:
        path_resp = f"runs/scenario_{current_scenario:.1f}/{test_run_id}/responses/responses.json"
    else:
        os.makedirs(f"runs/scenario_{current_scenario:.1f}", exist_ok=True)
        path_resp = f"runs/scenario_{current_scenario:.1f}/unknown_run_responses.json"

    try:
        existing = []
        if os.path.exists(path_resp):
            with open(path_resp, "r", encoding="utf-8") as fh:
                try:
                    existing = json.load(fh)
                    if not isinstance(existing, list):
                        existing = []
                except json.JSONDecodeError:
                    existing = []

        existing.append(response_data)
        with open(path_resp, "w", encoding="utf-8") as fh:
            json.dump(existing, fh, indent=2)

        logging.info("[store_response] Appended request/response => %s", path_resp)

    except Exception as exc:
        logging.error("[store_response] Failed to store => %s", exc)


def load_followed_users(scenario: float) -> set:
    """Load previously followed users for this scenario"""
    global followed_users
    followed_users = set()
    
    # Path to followed users file
    scenario_dir = Path("runs") / f"scenario_{scenario:.1f}"
    followed_file = scenario_dir / "followed_users" / "followed.json"
    
    if followed_file.exists():
        try:
            with open(followed_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                followed_users.update(data.get("followed_users", []))
            logging.info(f"Loaded {len(followed_users)} previously followed users")
        except Exception as e:
            logging.error(f"Error loading followed users: {e}")
    
    return followed_users

async def add_followed_user(user_id: str, scenario: float) -> None:
    """Add a user to the followed users list and save to file"""
    global followed_users
    
    # Add to memory set
    followed_users.add(user_id)
    
    # Ensure directories exist
    scenario_dir = Path("runs") / f"scenario_{scenario:.1f}"
    followed_dir = scenario_dir / "followed_users"
    followed_dir.mkdir(parents=True, exist_ok=True)
    
    # Save to file
    followed_file = followed_dir / "followed.json"
    try:
        data = {"followed_users": list(followed_users)}
        with open(followed_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logging.info(f"Added user {user_id} to followed users")
    except Exception as e:
        logging.error(f"Error saving followed user: {e}")

def is_user_followed(user_id: str) -> bool:
    """Check if a user has already been followed"""
    return user_id in followed_users