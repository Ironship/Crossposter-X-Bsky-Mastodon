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
- **Optional GUI** for easy configuration and manual runs (requires `tkinter`).

## Configuration

### Authentication

Fill in the necessary keys and passwords in [settings/auth.py](settings/auth.py), **or use the GUI** (`python gui.py`) which lets you enter credentials through a graphical form and saves them for you:

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

To ignore specific tags when crossposting, add the tags you want to ignore to `ignore_tags_twitter` / `ignore_tags_mastodon` in [settings/settings.py](settings/settings.py).

## Installation and Running

### Prerequisites
- Python 3.10 or newer
- pip (Python package installer)
- `tkinter` (stdlib, usually pre-installed — on Debian/Ubuntu: `sudo apt install python3-tk`)

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

3. Configure your settings — either edit `settings/auth.py` and `settings/settings.py` directly, or use the GUI (see below).

### GUI (recommended for first-time setup)

Launch the graphical interface:
```bash
python gui.py
```

The GUI has three tabs:
- **Authentication** — enter and save your Bluesky, Mastodon, and Twitter/X credentials.
- **Settings** — toggle platforms, visibility, mention handling, rate-limit options, and more.
- **Run & Logs** — run the crossposter manually with a single click, watch live log output, and optionally enable automatic periodic runs.

### Running headless (no GUI)

#### On Windows
Run the included batch file: `run.bat`

This will start the crossposter and automatically run it every hour.

#### On Linux/macOS
Run the included shell script: `run.sh`

This will start the crossposter and automatically run it every hour.

#### Manually (single run)
```bash
python crosspost.py
```


## TODO

- Check and fix Docker configuration.
- Add support for optional long posts on Twitter by aggregating short Bluesky posts if Twitter Blue is active.
