Crossposter-X-Bsky-Mastodon
Crossposter-X-Bsky-Mastodon is a Python script that automatically crossposts your Bluesky posts to Mastodon and Twitter. The script can handle threads, quote posts, image posts (including alt text), and more. It is based on the bluesky-crossposter by Linus2punkt0.

Features
Automatically crossposts Bluesky posts to Mastodon and Twitter.
Handles threads, quote posts, and image posts with alt text.
Supports reposting your own posts.
Allows for quote posts of other users' posts with links to Bluesky.
Username handling to skip or clean up mentions.
Limits posts per hour and handles overflow posts.
Cross-deletion: deletes posts from Mastodon and Twitter if deleted on Bluesky within one hour.
Configuration
Authentication
Fill in the necessary keys and passwords in auth.py:

1 vulnerability
Settings
Configure the script behavior in settings.py:

Running the Script
To run the script, you can use the provided run.bat or run.sh scripts, or set up a cron job to run it periodically.

Docker
You can also run the script using Docker. Use the provided Dockerfile and docker-compose.yml to build and run the container. Configuration options can be set in the docker-compose.yml file or an .env file.

Usage
To start the crossposter, simply run:

Or use the provided run.bat or run.sh scripts.

License
This project is based on the bluesky-crossposter by Linus2punkt0.