# Crossposter-X-Bsky-Mastodon

Crossposter-X-Bsky-Mastodon is a Python script that automatically crossposts your Bluesky posts to Mastodon and Twitter. The script can handle threads, quote posts, image posts (including alt text), and more. It is based on the bluesky-crossposter by Linus2punkt0.

## Features

- Automatically crossposts Bluesky posts to Mastodon and Twitter.
- Handles threads, quote posts, and image posts with alt text.
- Supports reposting your own posts.
- Allows for quote posts of other users' posts with links to Bluesky.
- Username handling to skip or clean up mentions.
- Limits posts per hour and handles overflow posts.
- Cross-deletion: deletes posts from Mastodon and Twitter if deleted on Bluesky within one hour.
- Option to ignore specific tags when crossposting.

## Configuration

### Authentication

Fill in the necessary keys and passwords in [settings/auth.py](settings/auth.py):

```py
BSKY_HANDLE = "your_bluesky_handle"
BSKY_PASSWORD = "your_bluesky_password"
MASTODON_HANDLE = "your_mastodon_handle"
MASTODON_INSTANCE = "your_mastodon_instance"
MASTODON_TOKEN = "your_mastodon_token"
TWITTER_APP_KEY = "your_twitter_app_key"
TWITTER_APP_SECRET = "your_twitter_app_secret"
TWITTER_ACCESS_TOKEN = "your_twitter_access_token"
TWITTER_ACCESS_TOKEN_SECRET = "your_twitter_access_token_secret"
```

### Ignoring Tags

To ignore specific tags when crossposting, add the tags you want to ignore to the `IGNORE_TAGS` list in [settings/config.py](settings/config.py):

## Installation and Running

### Prerequisites
- Python 3.8 until 3.11 (I didnt test above 3.11)
- pip (Python package installer)

### Running

1. Clone the repository:
```bash
git clone https://github.com/yourusername/Crossposter-X-Bsky-Mastodon.git
cd Crossposter-X-Bsky-Mastodon
```

2. Install dependencies

```bash
pip install -r requirements.txt
```

3. Configure your settings in auth.py and settings.py

4. On Windows
Run the included batch file: run.bat

This will start the crossposter and automatically run it every hour.

On Linux/macOS
Run the included shell script: run.sh

This will start the crossposter and automatically run it every hour.


Running Manually
If you prefer to run the script manually once awhile just run:
```console
python crosspost.py
```


## TODO

- Implement an optional GUI if not running inside Docker.
- Check and fix Docker configuration.
- Upgrade Python version to the latest stable release.
- Add support for optional long posts on Twitter by aggregating short Bluesky posts if Twitter Blue is active.