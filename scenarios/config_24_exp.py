USE_PROXY = True
USE_LOGIN = True
REUSE_COOKIES = False
SCENARIO = 24.2
# Proxy country
COUNTRY = "United States"
# Endpoint settings
TARGET_ENDPOINT = "https://www.tiktok.com/api/recommend/item_list"
NUM_BATCHES = 3000
MAX_VIDEOS = 250
MAX_WATCHTIME = 120
# Proxy setup
PROXYHOST = ""
PROXYPORT = ""
PROXYUSERNAME = ""
PROXYPASSWORD = ""
PROXY = ""
# TikTok login credentials fetched from the DB
TIKTOK_EMAIL = ""
TIKTOK_PASSWORD = ""
# User profiles
USER_PROFILES = {
    22: {
        "HASHTAGS_TO_LIKE": [],
        "HASHTAGS_TO_FOLLOW": [],
        "WATCH_COEFFICIENT_WITH_HASHTAGS": 1,
        "WATCH_COEFFICIENT_NO_HASHTAGS": 1,
        "RANDOM_AUTHORS_TO_FOLLOW": 0,
        "RANDOM_POSTS_TO_LIKE": 0,
        "RANDOM_WATCH_COEFFICIENT": 0,
        "RANDOM_VIDEOS_TO_WATCH": 0,
        "USERNAMES_TO_FOLLOW": [],
        "USERNAMES_TO_LIKE": [ "noahbeck",
        "tb_davis",
        "barstoolsports",
        "Akila Eyewear",
        "truebloodbandofficial",
        "everybody_loves_cody",
        "thejuliapool",
        "velocity_templates",
        "cats.dogs.funny52",
        "richardoliver263",
        "mickeymunch",
        "blizzard_ae8",
        "nea.com",
        "travisscott",
        "boldpromises",
        "ren.lyrics",
        "stokestwins",
        "lizzza",
        "kirakosarin",
        "savv.labrant",
        "flighthouse",
        "arianagrande",
        "larrayeeee",
        "daviddobrik",
        "donaldducc",
        "kristenhancher",
        "lexibrookerivera",
        "jacobsartorius",
        "imkevinhart",
        "rosssmith",
        "livetv",
        "topperguild",
        "tonylopez",
        "kingbach",
        "hannahstocking",
        "camilo"],
        "HASHTAGS_WATCH_LONGER": [],
        "HASHTAGS_WATCH_LONGER_COEFFICIENT": 1,
    },
}


# Function to get user configuration
def get_user_config(user_id: int) -> dict:
    user_profile = USER_PROFILES.get(user_id, {})
    return {
        "HASHTAGS_TO_LIKE": user_profile.get("HASHTAGS_TO_LIKE", []),
        "HASHTAGS_TO_FOLLOW": user_profile.get("HASHTAGS_TO_FOLLOW", []),
        "WATCH_COEFFICIENT_WITH_HASHTAGS": user_profile.get("WATCH_COEFFICIENT_WITH_HASHTAGS", 1),
        "WATCH_COEFFICIENT_NO_HASHTAGS": user_profile.get("WATCH_COEFFICIENT_NO_HASHTAGS", 1),
        "RANDOM_AUTHORS_TO_FOLLOW": user_profile.get("RANDOM_AUTHORS_TO_FOLLOW", 0),
        "RANDOM_POSTS_TO_LIKE": user_profile.get("RANDOM_POSTS_TO_LIKE", 0),
        "RANDOM_WATCH_COEFFICIENT": user_profile.get("RANDOM_WATCH_COEFFICIENT", 0.0),
        "RANDOM_VIDEOS_TO_WATCH": user_profile.get("RANDOM_VIDEOS_TO_WATCH", 0),
        "USERNAMES_TO_FOLLOW": user_profile.get("USERNAMES_TO_FOLLOW", []),
        "USERNAMES_TO_LIKE": user_profile.get("USERNAMES_TO_LIKE", []),
        "HASHTAGS_WATCH_LONGER": user_profile.get("HASHTAGS_WATCH_LONGER", []),
        "HASHTAGS_WATCH_LONGER_COEFFICIENT": user_profile.get("HASHTAGS_WATCH_LONGER_COEFFICIENT", 1.2),
    }