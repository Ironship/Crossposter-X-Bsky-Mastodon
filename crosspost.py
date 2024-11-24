import traceback, sys
import arrow
from settings.auth import *
from settings.paths import *
from settings import settings
from local.functions import (
    cleanup,
    post_cache_read,
    post_cache_write,
    get_post_time_limit,
    check_rate_limit,
    logger,
)
from local.db import db_read, db_backup, save_db
from input.bluesky import get_posts
from output.post import post, delete
from input.bluesky import bsky_connect
from output.twitter import twitter_api


def run():
    if check_rate_limit():
        exit()
    database = db_read()
    post_cache = post_cache_read()
    # Putting all of the recently posted posts in a list and removing them as they are found in the timeline.
    # Any posts not found in the timeline are posts that have been deleted.
    deleted = list(post_cache.keys())
    timelimit = get_post_time_limit(post_cache)
    posts, deleted = get_posts(timelimit, deleted)
    logger.debug(post_cache)
    if deleted:
        database, post_cache = delete(deleted, post_cache, database)
        updates = True
    logger.debug(post_cache)
    updates, database, post_cache = post(posts, database, post_cache)
    post_cache_write(post_cache)
    if updates:
        save_db(database)
        cleanup()
    db_backup()
    if not posts:
        logger.info("No new posts found.")

    # Get Bluesky rate limit info
    bsky = bsky_connect()
    _, bsky_remaining, bsky_reset = bsky.get_rate_limit()
    if bsky_reset:
        bsky_reset_time = arrow.Arrow.fromtimestamp(bsky_reset).format("HH:mm:ss")
        logger.info(
            f"Bluesky API calls remaining: {bsky_remaining}, resets at: {bsky_reset_time}"
        )

    # Get Twitter rate limit info if Twitter posting is enabled
    if settings.Twitter:
        try:
            from output.twitter import twitter_api
            twitter_limits = twitter_api.rate_limit_status()
            
            # Get rate limits for status updates endpoint
            status_limits = twitter_limits.get('resources', {}).get('statuses', {})
            update_endpoint = next(
                (v for k, v in status_limits.items() if 'update' in k.lower()),
                None
            )

            if update_endpoint:
                twitter_reset_time = arrow.Arrow.fromtimestamp(
                    update_endpoint['reset']
                ).format("HH:mm:ss")
                twitter_remaining = update_endpoint['remaining']
                logger.info(
                    f"Twitter API calls remaining: {twitter_remaining}, resets at: {twitter_reset_time}"
                )
            else:
                logger.warning("Could not find status update endpoint rate limit info")
                
        except Exception as e:
            logger.error(f"Error getting Twitter rate limits: {e}")


# Here the whole thing is run
if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        logger.error(traceback.format_exc())
        sys.exit(-1)
