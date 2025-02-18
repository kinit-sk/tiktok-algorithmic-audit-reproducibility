"""
video_action_handler.py

This module defines the `VideoInteractor` class, which provides methods to interact 
with TikTok videos during automated scraping sessions. It includes functionalities 
for liking videos, following authors, simulating video watching, and performing 
randomized actions based on user configurations.

Classes:
    - VideoInteractor: Handles interactions with TikTok videos such as liking, following, 
      and watching based on provided configurations.

Features:
    - Like videos based on specific hashtags.
    - Follow authors based on specific hashtags.
    - Simulate watching videos and track watch time and percentage watched.
    - Perform random actions like liking or following within configured limits.

Usage:
    This class is typically instantiated with a browser tab object, video details, 
    and user configurations. It provides asynchronous methods to interact with videos 
    dynamically based on the scraped content.

Example:
    interactor = VideoInteractor(tab, video_element, video_details, video_index, user_config)
    await interactor.like_hashtags()
    await interactor.watch_video(coefficient=1.5)
"""

import asyncio
import logging

from nodriver import core
from scraper.tiktok_network_interceptor import (
    load_followed_users,
    add_followed_user,
    is_user_followed
)


class VideoInteractor:
    def __init__(
        self,
        tab: core.tab,
        video_element: core.element,
        video_details: dict,
        video_index: int,
        user_config: dict,
        scenario: float,  # Add scenario parameter
    ) -> None:
        self.tab = tab
        self.video_element = video_element
        self.video_details = video_details
        self.video_index = video_index
        self.user_config = user_config
        self.scenario = scenario  # Store scenario

        # Load followed users at initialization
        self.followed_users = load_followed_users(scenario)

        # Flags to track user actions
        self.followed_author = False
        self.time_watched = 0
        self.percentage_watched = 0.0
        self.liked_post = False

        # Track if we've performed actions
        self.liked = False

        # Get hashtags from video details (case-insensitive comparison)
        self.video_hashtags = [h.lower() for h in video_details.get("hashtags", [])]
        self.author_username = video_details.get("author_unique_id", "")
        self.author_username = self.author_username.lower().strip()
        logging.debug(
            "Initialized VideoInteractor with user_config: %s", self.user_config
        )

    async def should_like_video(self) -> bool:
        """Check if video should be liked based on hashtags or username"""

        # Debugging logs
        logging.info("Checking video for like: video_id=%s, author=%s, hashtags=%s",
                     self.video_details.get("video_id"), self.author_username, self.video_hashtags)

        # Check hashtags
        hashtags_to_like = [h.lower().strip() for h in self.user_config.get("HASHTAGS_TO_LIKE", [])]
        if any(h in self.video_hashtags for h in hashtags_to_like):
            logging.info("Video %s matched hashtags %s => LIKE", self.video_details.get("video_id"), hashtags_to_like)
            return True

        normalized_author = (
                self.video_details.get("author_unique_id", "")
        ).lower().strip()
        usernames_to_like = [u.lower().strip() for u in self.user_config.get("USERNAMES_TO_LIKE", [])]
        if normalized_author in usernames_to_like:
            logging.info("Video %s by '%s' matches username list => LIKE",
                         self.video_details.get("video_id"), normalized_author)
            return True

        return False

    async def should_follow_author(self) -> bool:
        """Check if author should be followed based on hashtags or username"""
        # Check hashtags
        hashtags_to_follow = [h.lower() for h in self.user_config.get("HASHTAGS_TO_FOLLOW", [])]
        if any(h in self.video_hashtags for h in hashtags_to_follow):
            return True

        # Check username
        usernames_to_follow = [u.lower() for u in self.user_config.get("USERNAMES_TO_FOLLOW", [])]
        if self.author_username in usernames_to_follow:
            return True

        return False

    async def handle_video_actions(self) -> None:
        """Handle all video actions - likes, follows based on hashtags and usernames"""
        try:
            # Check for hashtag/username based actions
            if await self.should_like_video():
                logging.info(
                    f"[VideoInteractor] Liking video {self.video_details['video_id']} based on hashtags/username"
                )
                await self.like()

            if await self.should_follow_author():
                logging.info(
                    f"[VideoInteractor] Following author {self.author_username} based on hashtags/username"
                )
                await self.follow_user()

        except Exception as e:
            logging.error(f"Error in handle_video_actions: {e}")

    async def like_hashtags(self) -> None:
        """Like the video based on specific hashtags from user_config."""
        try:
            hashtags = self.video_details.get("hashtags", [])
            if any(
                hashtag.lower()
                in (tag.lower() for tag in self.user_config["HASHTAGS_TO_LIKE"])
                for hashtag in hashtags
            ):
                await self.like()
                logging.info(
                    "Liked video %s based on hashtags %s",
                    self.video_details["video_id"],
                    hashtags,
                )
            else:
                logging.info(
                    "Video %s does not contain liked hashtags.",
                    self.video_details["video_id"],
                )
        except Exception as e:
            logging.error(
                "Error in like_hashtags for video %s: %s",
                self.video_details.get("video_id"),
                e,
            )

    async def like_video_by_username(self) -> None:
        """
        Like the video if the author's username appears in USERNAMES_TO_LIKE in user_config.
        """
        try:
            author_name = self.video_details.get("author_name", "")
            usernames_to_like = self.user_config.get("USERNAMES_TO_LIKE", [])

            if any(author_name.lower() == username.lower() for username in usernames_to_like):
                await self.like()
                logging.info(
                    "Liked video by user %s because it is in USERNAMES_TO_LIKE config.",
                    author_name
                )
            else:
                logging.info(
                    "Author %s not in USERNAMES_TO_LIKE list. No like action taken.",
                    author_name
                )
        except Exception as e:
            logging.error(
                "Error in like_video_by_username for user %s: %s",
                self.video_details.get("author_name"),
                e
            )

    async def follow_user_hashtags(self) -> None:
        """Follow the author based on specific hashtags from user_config."""
        try:
            hashtags = self.video_details.get("hashtags", [])
            if any(
                hashtag.lower()
                in (tag.lower() for tag in self.user_config["HASHTAGS_TO_FOLLOW"])
                for hashtag in hashtags
            ):
                await self.follow_user()
                self.followed_author = True
                logging.info(
                    "Followed user %s based on hashtags %s",
                    self.video_details["author_id"],
                    hashtags,
                )
            else:
                logging.info(
                    "Video %s does not contain follow hashtags.",
                    self.video_details["video_id"],
                )
        except Exception as e:
            logging.error(
                "Error in follow_user_hashtags for video %s: %s",
                self.video_details.get("video_id"),
                e,
            )

    async def follow_user_by_username(self) -> None:
        """
        Follow the author if the author's username appears in USERNAMES_TO_FOLLOW in user_config.
        """
        try:
            author_name = self.video_details.get("author_name", "")
            usernames_to_follow = self.user_config.get("USERNAMES_TO_FOLLOW", [])

            if any(author_name.lower() == username.lower() for username in usernames_to_follow):
                await self.follow_user()
                self.followed_author = True
                logging.info(
                    "Followed user %s because it is in USERNAMES_TO_FOLLOW config.",
                    author_name
                )
            else:
                logging.info(
                    "Author %s not in USERNAMES_TO_FOLLOW list. No follow action taken.",
                    author_name
                )
        except Exception as e:
            logging.error(
                "Error in follow_user_by_username for user %s: %s",
                self.video_details.get("author_name"),
                e
            )

    async def follow_user(self) -> None:
        """Attempt to follow the author of the video."""
        try:
            author_id = self.video_details.get("author_id")

            # Check if already followed
            if author_id and is_user_followed(author_id):
                logging.info(f"User {author_id} already followed, skipping")
                return

            script = f"""
            (function() {{
                var article = document.querySelector('article[data-scroll-index="{self.video_index}"]');
                if (article) {{
                    var followButton = article.querySelector('button[data-e2e="feed-follow"]');
                    if (followButton) {{
                        followButton.click();
                        return true;
                    }} else {{
                        return false;
                    }}
                }} else {{
                    return false;
                }}
            }})();
            """
            result = await self.tab.evaluate(script)
            if result:
                # Add to followed users immediately after successful follow
                await add_followed_user(author_id, self.scenario)
                self.followed_author = True
                logging.info("Followed user %s", author_id)
            else:
                logging.warning(
                    "Follow button not found for video %s",
                    self.video_details["video_id"],
                )
        except Exception as e:
            logging.error(
                "Error following user %s: %s",
                self.video_details.get("author_id"),
                e,
            )

    async def like(self) -> None:
        """Attempt to like the post."""
        try:
            script = f"""
            (function() {{
                var article = document.querySelector('article[data-scroll-index="{self.video_index}"]');
                if (article) {{
                    var likeButton = article.querySelector('button[aria-label^="Like video"]');
                    if (likeButton) {{
                        likeButton.click();
                        return true;
                    }} else {{
                        return false;
                    }}
                }} else {{
                    return false;
                }}
            }})();
            """
            result = await self.tab.evaluate(script)
            if result:
                self.liked_post = True
                logging.info("Liked video %s", self.video_details["video_id"])
            else:
                logging.warning(
                    "Like button not found for video %s",
                    self.video_details["video_id"],
                )
        except Exception as e:
            logging.error(
                "Error liking video %s: %s",
                self.video_details.get("video_id"),
                e,
            )

    async def watch_video(self, coefficient=1) -> None:
        """
        Simulate watching the video and track watch time.
        If the video matches any hashtags in HASHTAGS_WATCH_LONGER,
        override the watch coefficient using HASHTAGS_WATCH_LONGER_COEFFICIENT.
        """
        try:
            hashtags_watch_longer = self.user_config.get("HASHTAGS_WATCH_LONGER", [])
            longer_coefficient = self.user_config.get("HASHTAGS_WATCH_LONGER_COEFFICIENT", 1.2)

            video_hashtags = self.video_details.get("hashtags", [])
            if any(
                    hashtag.lower() in (tag.lower() for tag in hashtags_watch_longer)
                    for hashtag in video_hashtags
            ):
                logging.info(
                    "Video %s contains hashtags from HASHTAGS_WATCH_LONGER. "
                    "Overriding watch coefficient to %s",
                    self.video_details.get("video_id"),
                    longer_coefficient
                )
                coefficient = longer_coefficient

            await asyncio.sleep(1)  # brief wait to allow video playback to start

            duration = self.video_details.get("duration", 0.0)
            if not isinstance(duration, (int, float)):
                try:
                    duration = float(duration)
                except (TypeError, ValueError):
                    duration = 0.0

            # Evaluate the current time in the playing video
            current_time_script = f"""
            (function() {{
                var video = document.querySelector('article[data-scroll-index="{self.video_index}"] video');
                if (video) {{
                    return video.currentTime;
                }} else {{
                    return null;
                }}
            }})();
            """
            current_time = await self.tab.evaluate(current_time_script)
            if current_time is None:
                logging.warning(
                    "Could not retrieve currentTime for video %s. Assuming currentTime = 0.",
                    self.video_details["video_id"],
                )
                current_time = 0.0

            desired_watch_time = coefficient * duration
            remaining_time = desired_watch_time - current_time
            if remaining_time < 0:
                logging.info(
                    "Video %s has already played beyond desired watch time.",
                    self.video_details["video_id"],
                )
                remaining_time = 0.0

            logging.info(
                "CurrentTime: %.2fs, Desired: %.2fs, Remaining: %.2fs for video %s",
                current_time,
                desired_watch_time,
                remaining_time,
                self.video_details["video_id"],
            )

            # Wait the extra time if needed
            if remaining_time > 0:
                await asyncio.sleep(remaining_time)
                self.time_watched = int(remaining_time)
                self.percentage_watched = (
                    (self.time_watched / duration) * 100 if duration > 0 else 0.0
                )
                logging.info(
                    "Watched video %s for %ss (%.2f%%).",
                    self.video_details["video_id"],
                    self.time_watched,
                    self.percentage_watched,
                )
            else:
                logging.info(
                    "No need to wait more for video %s",
                    self.video_details["video_id"],
                )

        except Exception as e:
            logging.error(
                "Error in watch_video for video %s: %s",
                self.video_details.get("video_id"),
                e,
            )

    # New methods for random actions:
    async def follow_random(self) -> None:
        """Randomly follow an author if we still have quota for random follows."""
        try:
            if self.user_config["RANDOM_AUTHORS_TO_FOLLOW"] > 0:
                await self.follow_user()
                if self.followed_author:
                    self.user_config["RANDOM_AUTHORS_TO_FOLLOW"] -= 1
                    logging.info(
                        "Random follow performed. Remaining random follows: %s",
                        self.user_config["RANDOM_AUTHORS_TO_FOLLOW"],
                    )
                else:
                    logging.info(
                        "Could not perform random follow - follow button not found."
                    )
            else:
                logging.info("No remaining random follows allowed.")
        except Exception as e:
            logging.error(
                "Error in follow_random for video %s: %s",
                self.video_details.get("video_id"),
                e,
            )

    async def like_random(self) -> None:
        """Randomly like a video if we still have quota for random likes."""
        try:
            if self.user_config["RANDOM_POSTS_TO_LIKE"] > 0:
                await self.like()
                if self.liked_post:
                    self.user_config["RANDOM_POSTS_TO_LIKE"] -= 1
                    logging.info(
                        "Random like performed. Remaining random likes: %s",
                        self.user_config["RANDOM_POSTS_TO_LIKE"],
                    )
                else:
                    logging.info(
                        "Could not perform random like - like button not found."
                    )
            else:
                logging.info("No remaining random likes allowed.")
        except Exception as e:
            logging.error(
                "Error in like_random for video %s: %s",
                self.video_details.get("video_id"),
                e,
            )

    async def watch_random(self) -> None:
        """Randomly watch a portion of the video defined by RANDOM_WATCH_COEFFICIENT."""
        try:
            if (
                self.user_config["RANDOM_VIDEOS_TO_WATCH"] > 0
                and self.user_config["RANDOM_WATCH_COEFFICIENT"] > 0
            ):
                coefficient = self.user_config["RANDOM_WATCH_COEFFICIENT"]
                await self.watch_video(coefficient=coefficient)
                self.user_config["RANDOM_VIDEOS_TO_WATCH"] -= 1
                logging.info(
                    "Randomly watched %s at %s%% length. Remaining random partial watches: %s",
                    self.video_details["video_id"],
                    coefficient * 100,
                    self.user_config["RANDOM_VIDEOS_TO_WATCH"],
                )
            else:
                logging.info(
                    "No remaining random partial watches allowed or coefficient not set."
                )
        except Exception as e:
            logging.error(
                "Error in watch_random for video %s: %s",
                self.video_details.get("video_id"),
                e,
            )

    async def handle_random_follows(self, videos: list) -> None:
        """Handle random following of authors"""
        num_follows = self.user_config.get("RANDOM_AUTHORS_TO_FOLLOW", 0)
        if not num_follows:
            return

        follows_done = 0
        index = 0

        while follows_done < num_follows and index < len(videos):
            video = videos[index]
            author_id = video.get("author", {}).get("id")

            if author_id and not is_user_followed(author_id):
                try:
                    # Follow the user
                    await self.follow_user()
                    follows_done += 1
                except Exception as e:
                    logging.error(f"Error following user {author_id}: {e}")

            index += 1

        if follows_done < num_follows:
            logging.warning(
                f"Could only follow {follows_done} users out of {num_follows} requested "
                "(not enough new users available)"
            )