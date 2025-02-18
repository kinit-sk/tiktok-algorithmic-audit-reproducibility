"""
scenario_configs.py

This module contains predefined scenario and proxy configurations for different TikTok scraping runs.
Each scenario can have its own proxy settings and user profiles.
"""

SCENARIOS = {
40.1: {
        "proxy": {
            "host": "",
            "port": "",
            "username": "",
            "password": ""
        },
        "users": {
            39: {
                "email": "",
                "password": "",
                "settings": {
                    "USE_PROXY": True,
                    "USE_LOGIN": True,
                    "REUSE_COOKIES": True,
                    "COUNTRY": "United States",
                    "NUM_BATCHES": 2000,
                    "MAX_VIDEOS": 250,
                    "MAX_WATCHTIME": 120,
                    "HASHTAGS_WATCH_LONGER_MAXWATCHTIME": 120,
                    "RANDOM_WATCH_MAXWATCHTIME": 120,
                },
                "profile": {
                    "HASHTAGS_TO_LIKE": [],
                    "HASHTAGS_TO_FOLLOW": [],
                    "WATCH_COEFFICIENT_WITH_HASHTAGS": 1,
                    "WATCH_COEFFICIENT_NO_HASHTAGS": 1,
                    "RANDOM_AUTHORS_TO_FOLLOW": 0,
                    "RANDOM_POSTS_TO_LIKE": 0,
                    "RANDOM_WATCH_COEFFICIENT": 1,
                    "RANDOM_VIDEOS_TO_WATCH": 0,
                    "USERNAMES_TO_FOLLOW": [],
                    "USERNAMES_TO_LIKE": [],
                    "HASHTAGS_WATCH_LONGER": [],
                    "HASHTAGS_WATCH_LONGER_COEFFICIENT": 1,
                }
            }
        }
    },
    40.2: {
        "proxy": {
            "host": "",
            "port": "",
            "username": "",
            "password": ""
        },
        "users": {
            40: {
                "email": "",
                "password": "",
                "settings": {
                    "USE_PROXY": True,
                    "USE_LOGIN": True,
                    "REUSE_COOKIES": True,
                    "COUNTRY": "United States",
                    "NUM_BATCHES": 2000,
                    "MAX_VIDEOS": 250,
                    "MAX_WATCHTIME": 120,
                    "HASHTAGS_WATCH_LONGER_MAXWATCHTIME": 240,
                    "RANDOM_WATCH_MAXWATCHTIME": 120,
                },
                "profile": {
                    "HASHTAGS_TO_LIKE": [],
                    "HASHTAGS_TO_FOLLOW": [],
                    "WATCH_COEFFICIENT_WITH_HASHTAGS": 1,
                    "WATCH_COEFFICIENT_NO_HASHTAGS": 1,
                    "RANDOM_AUTHORS_TO_FOLLOW": 0,
                    "RANDOM_POSTS_TO_LIKE": 0,
                    "RANDOM_WATCH_COEFFICIENT": 1,
                    "RANDOM_VIDEOS_TO_WATCH": 0,
                    "USERNAMES_TO_FOLLOW": [],
                    "USERNAMES_TO_LIKE": [],
                    "HASHTAGS_WATCH_LONGER": ["football",
                                              "food",
                                              "championsleague",
                                              "movie",
                                              "foodtiktok",
                                              "gaming",
                                              "film",
                                              "tiktokfood",
                                              "gta6",
                                              "gta",
                                              "minecraft",
                                              "marvel",
                                              "cat",
                                              "dog",
                                              "pet",
                                              "dogsoftiktok",
                                              "catsoftiktok",
                                              "cute",
                                              "puppy",
                                              "dogs",
                                              "cats",
                                              "animals",
                                              "petsoftiktok",
                                              "kitten",
                                              "comedy",
                                              "asmr",
                                              "learnontiktok",
                                              "satisfying",
                                              "lol",
                                              "love",
                                              "humour",
                                              "couple",
                                              "foodie",
                                              "baby",
                                              "car",
                                              "cars",
                                              "jokes",
                                              "lifehack",
                                              "satisfyingvideo",
                                              "relationship",
                                              "cooking",
                                              "laugh",
                                              "fun",
                                              "roblox"],
                    "HASHTAGS_WATCH_LONGER_COEFFICIENT": 2,
                }
            }
        }
    },
}

def get_scenario_config(scenario: float, user_id: int) -> dict:
    """
    Get configuration for a specific scenario and user.
    Returns a complete config dictionary ready to use.
    """
    if scenario not in SCENARIOS:
        raise ValueError(f"Scenario {scenario} not found in configurations")

    scenario_config = SCENARIOS[scenario]
    if user_id not in scenario_config["users"]:
        raise ValueError(f"User {user_id} not found in scenario {scenario}")

    user_config = scenario_config["users"][user_id]

    return {
        # User-specific settings
        **user_config["settings"],
        **user_config["profile"],
        # Common settings
        "SCENARIO": scenario,
        "TARGET_ENDPOINT": "https://www.tiktok.com/api/recommend/item_list",
        # Proxy settings
        "PROXYHOST": scenario_config["proxy"]["host"],
        "PROXYPORT": scenario_config["proxy"]["port"],
        "PROXYUSERNAME": scenario_config["proxy"]["username"],
        "PROXYPASSWORD": scenario_config["proxy"]["password"],
        "PROXY": f"http://{scenario_config['proxy']['host']}:{scenario_config['proxy']['port']}",
        # User credentials and profile
        "TIKTOK_EMAIL": user_config["email"],
        "TIKTOK_PASSWORD": user_config["password"],
        "USER_PROFILES": {
            user_id: user_config["profile"]
        }
    }