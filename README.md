# Revisiting Algorithmic Audits of TikTok: Poor Reproducibility and Short-term Validity of Findings

---

This repository contains supplementary material for the paper Revisiting Algorithmic Audits of TikTok: Poor Reproducibility
and Short-term Validity of Findings

---

## Citing the paper
TBA

---
## Abstract

Social media platforms are shifting towards algorithmically curated content based on implicit or explicit user feedback while focusing more and more on short-format content. Regulators, as well as researchers, are calling for systematic social media algorithmic audits
as this shift leads to enclosing users in filter bubbles and leading
them to more problematic content. An important aspect of such
audits is the reproducibility and generalisability of their findings, as
it allows to draw verifiable conclusions and audit potential changes
in algorithms over time. In this work, we study the reproducibility of the existing audits of recommender systems in the popular
platform TikTok, and the generalizability of their findings. In our
efforts to reproduce the previous works, we find multiple challenges
stemming from social media platform changes and content evolution, but also the works themselves. These drawbacks limit the
audit reproducibility and require an extensive effort altogether with
inevitable adjustments to the auditing methodology. Our experiments also reveal that the audit findings often hold only in the
short term, implying that the reproducibility and generalizability
of the audits heavily depend on the methodological choices and the
state of algorithms and content on the platform. This highlights
the importance of longitudinal audits that allow us to determine how the situation changes in time, instead of the current practice of one-shot audits.

# Disclaimer
The code provided in this repository is made available for exploratory and replicative research purposes. Due to ongoing modifications to the TikTok web application and the evolving platform, some components may not function as intended without further modifications. Users are advised that periodic updates and adjustments might be necessary to maintain compatibility with the current state of the platform.

**[About us](https://kinit.sk/)**  
Repository for replicating the **[Investigation of Personalization Factors on TikTok](https://arxiv.org/abs/2201.12271)** with the **[nodriver](https://github.com/ultrafunkamsterdam/nodriver)** approach.

## Requirements

- Python 3.12+
- Git
- nodriver
- package manager (conda, uv)
- install the requirements

## Quick start

1. Clone the repository
2. Install the requirements (requirements.txt)
3. Configure scenarios in scenario_configs.py
4. Run parallel scraping with:
```bash
python parallel_runner.py
```

## Project structure
```
└── 📁nodriver
    └── 📁common
        └── proxy_auth.py
        └── response_utils.py
    └── 📁data - our data gathered from the platform
        └── 📁{scenario_id}
           └── 📁{scenario_id}-{user_type} (e.g., 9-control)
                └── 📁{test_run_id}
                    └── 📁interactions
                        └── {interaction_id}.json -> interaction data (likes, follows, etc.)
                    └── 📁responses
                        └── {response_id}.json -> response data (posts, streams, ads)
    └── 📁notebooks
        └── hashtags_interactions.ipynb
        └── main_analysis.ipynb
        └── nicknames_interactions.ipynb
        └── random_similarity.ipynb
    └── 📁runs - storage for runs
        └── 📁scenario_{scenario_id} -> Scenario folder
            └── 📁{test_run_id} -> Test run ID
                └── 📁invalid_jsons -> if we were unable to parse a .json
                └── 📁logs
                    └── run_{user_id}.log -> User-specific log file
                └── 📁requests -> .json files containing all requests
                └── 📁responses -> .json files containing all responses
                └── 📁screenshots -> screenshot of every post
                └── 📁streams_ads -> screenshots of streams and ads
                └── 📁invalid_jsons -> .json files that were not parsed correctly
                └── 📁interactions -> .json files containing all interactions (likes, follows, etc.)
    └── 📁scenarios -> folder with configs for scenarios
    └── 📁scraper
        └── fyp_browser.py
        └── tiktok_login.py
        └── tiktok_network_interceptor.py
        └── video_action_handler.py
    └── config_loader.py
    └── parallel_runner.py  
    └── requirements.txt  
    └── scenario_configs.py
    └── main.py
```

## scenario_configs.py example
```python
SCENARIOS = {
    151.1: {
        "proxy": {
            "host": "proxy_host", # proxy host
            "port": "proxy_port", # proxy port
            "username": "proxy_username", # proxy username
            "password": "proxy_password" # proxy password
        },
        "users": {
            user_id: {  # User ID
                "email": "user@example.com", # TikTok email
                "password": "user_pass", # TikTok password
                "settings": {
                    "USE_PROXY": True, # Use proxy
                    "USE_LOGIN": True, # Use login
                    "REUSE_COOKIES": False, # Reuse cookies
                    "COUNTRY": "United States", # Country
                    "NUM_BATCHES": 3000, # Maximum number of batches - we suggest to keep this high and set MAX_VIDEOS to a specific number as size of batches varies
                    "MAX_VIDEOS": 250, # Maximum number of videos
                    "MAX_WATCHTIME": 120, # Maximum watch time in seconds
                    "HASHTAGS_WATCH_LONGER_MAXWATCHTIME": 240 # Maximum watch time for hashtags to watch longer
                    "RANDOM_WATCH_MAXWATCHTIME": 120 # Maximum watch time for random videos scenario
                },
                "profile": {
                    "HASHTAGS_TO_LIKE": [], # Hashtags to like
                    "HASHTAGS_TO_FOLLOW": [], # Hashtags to follow
                    "WATCH_COEFFICIENT_WITH_HASHTAGS": 1, # Watch coefficient with hashtags
                    "WATCH_COEFFICIENT_NO_HASHTAGS": 1, # Watch coefficient without hashtags
                    "RANDOM_AUTHORS_TO_FOLLOW": 0, # Random authors to follow
                    "RANDOM_POSTS_TO_LIKE": 0, # Random posts to like
                    "RANDOM_VIDEOS_TO_WATCH": 0, # Random videos to watch
                    "RANDOM_WATCH_COEFFICIENT": 1.0, # Random watch coefficient
                    "USERNAMES_TO_FOLLOW": [], # Usernames to follow
                    "USERNAMES_TO_LIKE": [], # Usernames to like
                    "HASHTAGS_WATCH_LONGER": [], # Hashtags to watch longer
                    "HASHTAGS_WATCH_LONGER_COEFFICIENT": 1, # Hashtags watch longer coefficient
                }
            }
        }
    }
}
```

## Key Features

1. **Parallel Execution**
   - Runs multiple TikTok scraping instances simultaneously - we tested up to 4 instances at the same time
   - Each instance has its own configuration and scenario
   - Configurable delay between instance starts - to deal with issues during logging manually if necessary

2. **Scenario-Based Configuration**
   - Each scenario has its own proxy settings - we used [webshare](https://webshare.io/) proxies
   - User-specific settings for each scenario
   - Flexible configuration of interaction behaviors

3. **Network Interception & Data Collection**
   - Captures TikTok's network events
   - Stores requests and responses in scenario-specific folders
   - Takes screenshots of posts, streams, and ads

4. **User Actions**
   - Configurable video watching durations
   - Optional liking and following behaviors
   - Support for hashtag-based interactions

5. **Logging System**
   - Separate log files for each parallel run
   - Scenario-specific folder structure
   - Detailed logging of all actions and events

6. **Error Handling**
   - Graceful handling of failed runs
   - Invalid JSON storage for debugging
   - Automatic cleanup of temporary files

## Running Multiple Scenarios

To run multiple scenarios in parallel:

1. Define scenarios in scenario_configs.py
2. Configure the runs in parallel_runner.py:
```python
runs = [
    (151.1, 3),  # (scenario_id, user_id) from scenario_configs.py
    (151.2, 5),
    (9.1, 1),
    (9.2, 2)
]
```
3. Run with:
```bash
python parallel_runner.py
```

Each scenario will run in parallel with its own configuration and store data in its respective folder.

## Jupyter notebooks descriptions
- **main_analysis.ipynb**: Consists of analysis to measure noise and location impact and analysis to compare feeds similarities (control vs. personalized, beginning vs. end, etc.)

- **hashtags_interactions.ipynb**:  Analyzes target hashtags in experimental vs. control groups

- **nicknames_interactions.ipynb**:  Examines nickname occurrences in experimental vs. control groups

- **random_similarity.ipynb**:  Measures hashtag similarity between experimental and control groups using bucket-based comparisons

---