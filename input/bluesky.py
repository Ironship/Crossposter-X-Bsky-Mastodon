import os
import arrow
from loguru import logger
from settings import settings
from settings.auth import BSKY_HANDLE, BSKY_PASSWORD
from settings.paths import session_cache_path
from local.functions import (
    RateLimitedClient,
    lang_toggle,
    rate_limit_write,
    session_cache_read,
    session_cache_write,
    on_session_change,
)

DATE_FORMAT = "YYYY-MM-DDTHH:mm:ss"


def bsky_connect():
    """
    Establish a connection to Bluesky, handling session management and rate limits.

    Returns:
        RateLimitedClient: An authenticated Bluesky client instance.
    """
    try:
        bsky = RateLimitedClient()
        bsky.on_session_change(on_session_change)
        session = session_cache_read()
        if session:
            logger.info("Connecting to Bluesky using saved session.")
            bsky.login(session_string=session)
        else:
            logger.info("Creating new Bluesky session using username and password.")
            bsky.login(BSKY_HANDLE, BSKY_PASSWORD)
        session_cache_write(bsky.export_session_string())
        return bsky
    except Exception as e:
        logger.error(f"Error connecting to Bluesky: {e}")
        if hasattr(e, "response") and hasattr(e.response, "content"):
            if e.response.content.error == "RateLimitExceeded":
                ratelimit_reset = e.response.headers.get("RateLimit-Reset")
                rate_limit_write(ratelimit_reset)
            elif e.response.content.error == "ExpiredToken":
                logger.info("Session expired, removing session file.")
                if os.path.exists(session_cache_path):
                    os.remove(session_cache_path)
        exit()

def remove_tags(text):
    """
    Removes hashtags from the text.

    Args:
        text (str): The text containing hashtags.

    Returns:
        str: Text with hashtags removed.
    """
    # Split text into words and filter out hashtags
    words = text.split()
    filtered_words = [word for word in words if not word.startswith('#')]
    return ' '.join(filtered_words)


def get_posts(timelimit=None, deleted_cids=None):
    """
    Fetches posts from Bluesky within a specified time limit and processes them for cross-posting.

    Args:
        timelimit (arrow.Arrow, optional): The time limit for fetching posts. Defaults to one hour ago.
        deleted_cids (list, optional): List of post CIDs that have been deleted. Defaults to an empty list.

    Returns:
        tuple: A dictionary of processed posts and a list of deleted CIDs.
    """
    if timelimit is None:
        timelimit = arrow.utcnow().shift(hours=-1)
    if deleted_cids is None:
        deleted_cids = []

    bsky = bsky_connect()
    logger.info("Gathering posts from Bluesky.")
    posts = {}

    # Getting feed of user
    profile_feed = bsky.app.bsky.feed.get_author_feed({"actor": BSKY_HANDLE})
    visibility_setting = settings.visibility

    for feed_view in profile_feed.feed:
        # Skip reposts from other accounts
        if feed_view.post.author.handle != BSKY_HANDLE:
            continue

        # Determine if the post is a repost
        is_repost = hasattr(feed_view.reason, "indexed_at")
        created_at = get_post_created_at(feed_view, is_repost)

        # Determine if the post should be crossposted based on language settings
        langs = feed_view.post.record.langs
        text = feed_view.post.record.text
        orig_text = text

        # Check Twitter ignore tags
        twitter_post = settings.Twitter and lang_toggle(langs, "twitter")
        if twitter_post:
            twitter_post = not check_ignored_tags(text, "twitter")

        # Check Mastodon ignore tags
        mastodon_post = settings.Mastodon and lang_toggle(langs, "mastodon")
        if mastodon_post:
            mastodon_post = not check_ignored_tags(text, "mastodon")

        # Remove tags if post will be crossposted
        if twitter_post or mastodon_post:
            text = remove_tags(text)

        if not mastodon_post and not twitter_post:
            continue

        cid = feed_view.post.cid

        # Remove ignored tags from text
        text, has_ignored_tag = remove_ignored_tags(text)

        # Skip posts with ignored tags
        if has_ignored_tag:
            logger.info(
                f"Post with CID {cid} contains ignored tags and will not be posted."
            )
            continue

        # Update deleted_cids if the post is no longer in the timeline
        if cid in deleted_cids:
            deleted_cids.remove(cid)

        # Process facets (URLs, mentions)
        send_mention = True
        if feed_view.post.record.facets:
            text = restore_urls(feed_view.post.record, text)
            text, send_mention = handle_mentions(feed_view.post.record, text)
        if not send_mention:
            continue

        # Handle replies and quotes
        reply_to_user = BSKY_HANDLE
        reply_to_post = ""
        quoted_post = ""
        quote_url = ""
        allowed_reply = get_allowed_reply(feed_view.post)

        if is_quote_post(feed_view.post):
            try:
                quoted_user, quoted_post, quote_url, is_open = get_quote_post_info(
                    feed_view.post.embed.record
                )
            except Exception as e:
                logger.error(f"Cannot parse quoted post in CID {cid}: {e}")
                continue
            if not should_crosspost_quote(quoted_user, is_open):
                continue
            if quoted_user == BSKY_HANDLE:
                text = text.replace(quote_url, "")

        if feed_view.post.record.reply:
            reply_to_post = feed_view.post.record.reply.parent.cid
            reply_to_user = get_reply_to_user(feed_view, bsky)

        if not reply_to_user:
            logger.info(
                f"Unable to find the user that post {cid} replies to or quotes."
            )
            continue

        # Check if the post is within the time limit and not a reply to someone else
        if created_at > timelimit and reply_to_user == BSKY_HANDLE:
            media = get_media_info(feed_view)
            visibility = determine_visibility(visibility_setting, reply_to_post)
            post_info = create_post_info(
                text=text,
                reply_to_post=reply_to_post,
                quoted_post=quoted_post,
                quote_url=quote_url,
                media=media,
                visibility=visibility,
                twitter=twitter_post,
                mastodon=mastodon_post,
                allowed_reply=allowed_reply,
                is_repost=is_repost,
                timestamp=created_at,
            )
            logger.debug(f"Processed post info: {post_info}")
            posts[cid] = post_info

    return posts, deleted_cids


def get_post_created_at(feed_view, is_repost):
    """
    Retrieves the creation time of a post.

    Args:
        feed_view: The feed view object containing the post.
        is_repost (bool): Indicates if the post is a repost.

    Returns:
        arrow.Arrow: The creation time of the post.
    """
    if is_repost:
        created_at_str = feed_view.reason.indexed_at.split(".")[0]
    else:
        created_at_str = feed_view.post.record.created_at.split(".")[0]
    return arrow.get(created_at_str, DATE_FORMAT)


def remove_ignored_tags(text):
    """
    Removes ignored tags from the post text and checks if any were found.

    Args:
        text (str): The original post text.

    Returns:
        tuple: Updated text and a boolean indicating if ignored tags were found.
    """
    found_ignored_tag = False
    for tag in settings.ignore_tags_twitter + settings.ignore_tags_mastodon:
        if tag in text:
            found_ignored_tag = True
        text = text.replace(tag, "").strip()
    return text, found_ignored_tag


def handle_mentions(record, text):
    """
    Processes mentions in the post text based on settings.

    Args:
        record: The post record containing facets.
        text (str): The original post text.

    Returns:
        tuple: The updated text and a boolean indicating if the post should be sent.
    """
    send_mention = True
    encoded_text = text.encode("UTF-8")
    for facet in record.facets:
        if facet.features[0].py_type != "app.bsky.richtext.facet#mention":
            continue
        start = facet.index.byte_start
        end = facet.index.byte_end
        username = encoded_text[start:end].decode("UTF-8")
        if settings.mentions == "skip":
            send_mention = False
            break
        elif settings.mentions == "strip":
            text = text.replace(username, username.replace("@", ""))
        elif settings.mentions == "url":
            base_url = "https://bsky.app/profile/"
            did = facet.features[0].did
            url = f"{base_url}{did}"
            text = text.replace(username, url)
    return text, send_mention


def is_quote_post(post):
    """
    Checks if a post is a quote post.

    Args:
        post: The post object.

    Returns:
        bool: True if the post is a quote post, False otherwise.
    """
    return post.embed and hasattr(post.embed, "record")


def get_quote_post_info(embed_record):
    """
    Retrieves information about the quoted post.

    Args:
        embed_record: The embedded record of the quoted post.

    Returns:
        tuple: Quoted user's handle, quoted post's CID, quote URL, and openness status.
    """
    try:
        if hasattr(embed_record, "author"):
            # Accessing attributes directly since embed_record.author is an object
            author = embed_record.author
            user = getattr(author, "handle", None)
            cid = getattr(embed_record, "cid", None)
            uri = getattr(embed_record, "uri", None)
            labels = getattr(author, "labels", [])
        else:
            # Assuming embed_record["record"]["author"] is a dict
            author = embed_record["record"]["author"]
            if isinstance(author, dict):
                user = author.get("handle")
                cid = embed_record["record"].get("cid")
                uri = embed_record["record"].get("uri")
                labels = author.get("labels", [])
            else:
                # If author is not a dict, attempt attribute access
                user = getattr(author, "handle", None)
                cid = getattr(embed_record["record"], "cid", None)
                uri = getattr(embed_record["record"], "uri", None)
                labels = getattr(author, "labels", [])

        # Ensure that all necessary fields are present
        if not all([user, cid, uri]):
            logger.error(
                f"Missing necessary fields in embed_record: user={user}, cid={cid}, uri={uri}"
            )
            raise ValueError("Incomplete embed_record data.")

        # Determine if the quoted post is open to unauthenticated users
        is_open = not any(
            getattr(label, "val", "") == "!no-unauthenticated" for label in labels
        )

        # Construct the URL to the quoted post
        post_id = uri.split("/")[-1] if "/" in uri else uri
        url = f"https://bsky.app/profile/{user}/post/{post_id}"

        return user, cid, url, is_open

    except AttributeError as e:
        logger.error(f"Attribute error in get_quote_post_info: {e}")
        raise
    except KeyError as e:
        logger.error(f"Key error in get_quote_post_info: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_quote_post_info: {e}")
        raise


def should_crosspost_quote(quoted_user, is_open):
    """
    Determines if a quoted post should be crossposted.

    Args:
        quoted_user (str): The handle of the quoted user.
        is_open (bool): Whether the quoted post is open to unauthenticated users.

    Returns:
        bool: True if the post should be crossposted, False otherwise.
    """
    if quoted_user != BSKY_HANDLE and (not settings.quote_posts or not is_open):
        return False
    return True


def get_reply_to_user(feed_view, bsky):
    """
    Retrieves the handle of the user being replied to.

    Args:
        feed_view: The feed view object containing the post.
        bsky: The Bluesky client instance.

    Returns:
        str: The handle of the user being replied to.
    """
    try:
        return feed_view.reply.parent.author.handle
    except AttributeError:
        return bsky.get_reply_to_user(feed_view.post.record.reply.parent)


def get_media_info(feed_view):
    """
    Extracts media information from a feed view.

    Args:
        feed_view: The feed view object containing the post.

    Returns:
        dict: A dictionary containing media type and data.
    """
    media = {}
    post_embed = feed_view.post.embed
    post_record_embed = getattr(feed_view.post.record, "embed", None)

    if hasattr(post_embed, "images"):
        media = {
            "type": "image",
            "data": [
                {"url": img.fullsize, "alt": img.alt} for img in post_embed.images
            ],
        }
    elif hasattr(post_embed, "media") and hasattr(post_embed.media, "images"):
        media = {
            "type": "image",
            "data": [
                {"url": img.fullsize, "alt": img.alt} for img in post_embed.media.images
            ],
        }
    elif post_record_embed and hasattr(post_record_embed, "video"):
        video_data = get_video_data(feed_view)
        media = {
            "type": "video",
            "data": video_data,
        }
    # Include external links not present in text
    if (
        post_embed
        and hasattr(post_embed, "external")
        and hasattr(post_embed.external, "uri")
    ):
        external_uri = post_embed.external.uri
        if external_uri not in feed_view.post.record.text:
            feed_view.post.record.text += f"\n{external_uri}"
    return media


def determine_visibility(visibility_setting, reply_to_post):
    """
    Determines the visibility of the post based on settings.

    Args:
        visibility_setting (str): The default visibility setting.
        reply_to_post (str): The CID of the post being replied to.

    Returns:
        str: The determined visibility ("public", "unlisted", etc.).
    """
    if visibility_setting == "hybrid" and reply_to_post:
        return "unlisted"
    elif visibility_setting == "hybrid":
        return "public"
    return visibility_setting


def create_post_info(**kwargs):
    """
    Creates a dictionary containing post information.

    Args:
        **kwargs: Keyword arguments containing post details.

    Returns:
        dict: A dictionary containing post information.
    """
    return {
        "text": kwargs.get("text"),
        "reply_to_post": kwargs.get("reply_to_post"),
        "quoted_post": kwargs.get("quoted_post"),
        "quote_url": kwargs.get("quote_url"),
        "media": kwargs.get("media"),
        "visibility": kwargs.get("visibility"),
        "twitter": kwargs.get("twitter"),
        "mastodon": kwargs.get("mastodon"),
        "allowed_reply": kwargs.get("allowed_reply"),
        "repost": kwargs.get("is_repost"),
        "timestamp": kwargs.get("timestamp"),
    }


def get_allowed_reply(post):
    """
    Determines who is allowed to reply to the post.

    Args:
        post: The post object.

    Returns:
        str: The reply restriction ("All", "None", "Following", "Mentioned", "Unknown").
    """
    threadgate = post.threadgate
    if not threadgate:
        return "All"
    allowed_rules = threadgate.record.allow
    if not allowed_rules:
        return "None"
    rule_type = allowed_rules[0].py_type
    if rule_type == "app.bsky.feed.threadgate#followingRule":
        return "Following"
    if rule_type == "app.bsky.feed.threadgate#mentionRule":
        return "Mentioned"
    return "Unknown"


def restore_urls(record, text):
    """
    Restores shortened URLs in the post text.

    Args:
        record: The post record containing facets.
        text (str): The original post text.

    Returns:
        str: The text with URLs restored.
    """
    encoded_text = text.encode("UTF-8")
    for facet in record.facets:
        if facet.features[0].py_type != "app.bsky.richtext.facet#link":
            continue
        url = facet.features[0].uri
        start = facet.index.byte_start
        end = facet.index.byte_end
        shortened = encoded_text[start:end].decode("UTF-8")
        text = text.replace(shortened, url)
    return text


def get_video_data(feed_view):
    """
    Retrieves video data from a feed view.

    Args:
        feed_view: The feed view object containing the post.

    Returns:
        dict: A dictionary containing video URL and alt text.
    """
    did = feed_view.post.author.did
    blob_cid = feed_view.post.record.embed.video.ref.link
    url = f"https://bsky.social/xrpc/com.atproto.sync.getBlob?did={did}&cid={blob_cid}"
    alt = feed_view.post.record.embed.alt or ""
    return {"url": url, "alt": alt}

def check_ignored_tags(text, platform):
    """Check if text contains any ignored tags for the specified platform"""
    tags = (settings.ignore_tags_twitter if platform == "twitter"
            else settings.ignore_tags_mastodon)
    for tag in tags:
        if tag in text:
            return True
    return False
