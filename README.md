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
