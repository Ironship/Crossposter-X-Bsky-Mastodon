import tweepy
import time
from loguru import logger
from settings import settings
from settings.auth import *

if settings.Twitter:
    # OAuth 1.0a User Authentication
    tweepy_auth = tweepy.OAuth1UserHandler(
        TWITTER_APP_KEY,
        TWITTER_APP_SECRET,
        TWITTER_ACCESS_TOKEN,
        TWITTER_ACCESS_TOKEN_SECRET,
    )
    twitter_api = tweepy.API(tweepy_auth)

    # Initialize Client with OAuth 1.0a credentials
    twitter_client = tweepy.Client(
        consumer_key=TWITTER_APP_KEY,
        consumer_secret=TWITTER_APP_SECRET,
        access_token=TWITTER_ACCESS_TOKEN,
        access_token_secret=TWITTER_ACCESS_TOKEN_SECRET,
        wait_on_rate_limit=False,  # Disable automatic rate limit handling
    )


def set_reply_settings(allowed_reply):
    """
    Determines the reply settings for a tweet based on the allowed replies.
    """
    if allowed_reply in ("None", "Mentioned"):
        return "mentionedUsers"
    elif allowed_reply == "Following":
        return "following"
    else:
        return None


def upload_media(media_items):
    """
    Uploads media files to Twitter and returns a list of media IDs.
    """
    media_ids = []
    for item in media_items:
        alt_text = item.get("alt", "")
        if len(alt_text) > 1000:
            alt_text = alt_text[:996] + "..."
        filename = item["filename"]
        res = twitter_api.media_upload(filename)
        media_id = res.media_id
        if alt_text:
            logger.info(f"Uploading media '{filename}' with ALT text to Twitter")
            twitter_api.create_media_metadata(media_id, alt_text)
        media_ids.append(media_id)
    return media_ids


def split_text_into_tweets(text, max_length=280):
    """
    Splits the text into a list of tweets, each not exceeding max_length.
    """
    logger.info("Splitting post that is too long for Twitter.")
    words = text.split()
    tweets = []
    current_tweet = ""
    for word in words:
        # +1 accounts for the space character
        if len(current_tweet) + len(word) + 1 <= max_length:
            current_tweet += (" " if current_tweet else "") + word
        else:
            tweets.append(current_tweet)
            current_tweet = word
    if current_tweet:
        tweets.append(current_tweet)
    return tweets


def post_tweet(
    text,
    reply_settings=None,
    quote_tweet_id=None,
    in_reply_to_tweet_id=None,
    media_ids=None,
):
    """
    Posts a single tweet to Twitter.
    """
    response = twitter_client.create_tweet(
        text=text,
        reply_settings=reply_settings,
        quote_tweet_id=quote_tweet_id,
        in_reply_to_tweet_id=in_reply_to_tweet_id,
        media_ids=media_ids,
        user_auth=True,
    )
    tweet_id = response.data["id"]
    logger.info(f"Tweet posted to Twitter with ID {tweet_id}")
    return tweet_id


def post_thread(text, initial_reply_to_id=None, media_ids=None):
    """
    Posts a thread of tweets if the text exceeds Twitter's character limit.
    """
    tweets = split_text_into_tweets(text)
    previous_tweet_id = initial_reply_to_id
    for idx, tweet_text in enumerate(tweets):
        # Attach media only to the first tweet in the thread
        media = media_ids if idx == 0 else None
        tweet_id = post_tweet(
            text=tweet_text, in_reply_to_tweet_id=previous_tweet_id, media_ids=media
        )
        previous_tweet_id = tweet_id
        logger.info(f"Posted part {idx + 1}/{len(tweets)} to Twitter")
    return previous_tweet_id


def tweet(
    post_text, reply_to_post=None, quote_post=None, media=None, allowed_reply=None
):
    """
    Posts a tweet or thread to Twitter, handling exceptions and retries.
    """
    MAX_RETRIES = 3
    retries = 0
    reply_settings = set_reply_settings(allowed_reply)
    media_ids = upload_media(media) if media else None

    while retries <= MAX_RETRIES:
        try:
            # Attempt to post the tweet
            tweet_id = post_tweet(
                text=post_text,
                reply_settings=reply_settings,
                quote_tweet_id=quote_post,
                in_reply_to_tweet_id=reply_to_post,
                media_ids=media_ids,
            )
            return tweet_id
        except tweepy.errors.BadRequest as e:
            # Handle tweets that are too long
            if "Too long" in str(e):
                logger.warning(
                    "Tweet is too long. Attempting to split and repost as a thread."
                )
                tweet_id = post_thread(post_text, reply_to_post, media_ids)
                return tweet_id
            else:
                logger.error(f"BadRequest Error while posting tweet: {e}")
                retries += 1
        except tweepy.errors.TooManyRequests:
            # Handle rate limits by skipping Twitter posting
            logger.error("Rate limit exceeded on Twitter. Skipping Twitter posting.")
            return None  # Exit the function without retrying
        except tweepy.errors.TweepyException as e:
            # Handle other Tweepy exceptions
            logger.error(f"TweepyException occurred: {e}")
            retries += 1
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            retries += 1
    logger.error("Maximum retry limit reached. Skipping post.")
    return None


def retweet(tweet_id):
    """
    Retweets a tweet by its ID.
    """
    try:
        twitter_client.retweet(tweet_id, user_auth=True)
        logger.info(f"Retweeted tweet {tweet_id}")
    except tweepy.errors.TooManyRequests:
        logger.error("Rate limit exceeded on Twitter. Skipping retweet.")
    except tweepy.errors.TweepyException as e:
        logger.error(f"TweepyException occurred while retweeting: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred while retweeting: {e}")


def delete(tweet_id):
    """
    Deletes a tweet by its ID.
    """
    logger.info(f"Deleting tweet with ID {tweet_id}")
    try:
        twitter_api.destroy_status(tweet_id)
        logger.info(f"Tweet {tweet_id} deleted")
    except tweepy.errors.TooManyRequests:
        logger.error("Rate limit exceeded on Twitter. Skipping deletion.")
    except tweepy.errors.TweepyException as e:
        logger.error(f"TweepyException occurred while deleting: {e}")
        if "No status found with that ID" in str(e):
            logger.info(f"Tweet with ID {tweet_id} does not exist")
    except Exception as e:
        logger.error(f"An unexpected error occurred while deleting: {e}")
