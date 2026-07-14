"""
CreatorForge OS v3.0 — Platform Connectors
============================================
Real-world platform integrations that let agents take real actions:
- Post to Instagram (photos, reels, stories, carousels)
- Upload to YouTube (videos with metadata)
- Send real emails (SMTP)
- Create Stripe invoices and payment links
- Post to Twitter/X
- Send Slack/Discord notifications
- Create calendar events
- Create GitHub issues

Each connector stores credentials encrypted in the database.
Agents call these through action tools in agent_tools.py.
"""
import os
import json
import smtplib
import ssl
import asyncio
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta
from typing import Optional, Any
from cryptography.fernet import Fernet

from models import db_cursor

logger = logging.getLogger(__name__)

# ── Encryption for storing credentials ──
ENCRYPTION_KEY_FILE = os.path.join(os.path.dirname(__file__), ".enc_key")


def _get_encryption_key() -> bytes:
    """Get or create the encryption key for platform credentials."""
    if os.path.exists(ENCRYPTION_KEY_FILE):
        with open(ENCRYPTION_KEY_FILE, "rb") as f:
            return f.read()
    key = Fernet.generate_key()
    # Ensure we can write to the directory
    try:
        with open(ENCRYPTION_KEY_FILE, "wb") as f:
            f.write(key)
        os.chmod(ENCRYPTION_KEY_FILE, 0o600)
    except Exception:
        pass
    return key


def encrypt_credentials(data: dict) -> str:
    """Encrypt credential dict for storage."""
    key = _get_encryption_key()
    f = Fernet(key)
    return f.encrypt(json.dumps(data).encode()).decode()


def decrypt_credentials(encrypted: str) -> dict:
    """Decrypt stored credentials."""
    key = _get_encryption_key()
    f = Fernet(key)
    return json.loads(f.decrypt(encrypted.encode()).decode())


# ═══════════════════════════════════════════════════════════════
#  Credential Storage
# ═══════════════════════════════════════════════════════════════

def store_platform_credential(platform: str, credentials: dict):
    """Store encrypted credentials for a platform."""
    encrypted = encrypt_credentials(credentials)
    with db_cursor() as conn:
        conn.execute("""
            INSERT INTO platform_credentials (platform, credentials, status, created_at, updated_at)
            VALUES (?, ?, 'connected', datetime('now'), datetime('now'))
            ON CONFLICT(platform) DO UPDATE SET
                credentials = excluded.credentials,
                status = 'connected',
                updated_at = datetime('now')
        """, (platform, encrypted))


def get_platform_credential(platform: str) -> Optional[dict]:
    """Get decrypted credentials for a platform."""
    with db_cursor() as conn:
        row = conn.execute(
            "SELECT credentials, status FROM platform_credentials WHERE platform = ?",
            (platform,)
        ).fetchone()
        if not row or row["status"] != "connected":
            return None
        return decrypt_credentials(row["credentials"])


def get_connected_platforms() -> list:
    """Get list of all connected platforms."""
    with db_cursor() as conn:
        rows = conn.execute(
            "SELECT platform, status, created_at FROM platform_credentials ORDER BY platform"
        ).fetchall()
        return [dict(r) for r in rows]


def disconnect_platform(platform: str):
    """Disconnect a platform."""
    with db_cursor() as conn:
        conn.execute(
            "UPDATE platform_credentials SET status = 'disconnected', updated_at = datetime('now') WHERE platform = ?",
            (platform,)
        )


# ═══════════════════════════════════════════════════════════════
#  Platform Action Log
# ═══════════════════════════════════════════════════════════════

def log_platform_action(platform: str, action: str, status: str, details: str = "",
                         agent_name: str = None, entity_type: str = None, entity_id: int = None):
    """Log a platform action for audit trail."""
    with db_cursor() as conn:
        conn.execute("""
            INSERT INTO platform_actions (platform, action, status, details, agent_name, entity_type, entity_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (platform, action, status, details, agent_name, entity_type, entity_id))


def get_platform_actions(limit: int = 50) -> list:
    """Get recent platform actions."""
    with db_cursor() as conn:
        rows = conn.execute(
            "SELECT * FROM platform_actions ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════════════
#  EMAIL Connector (SMTP)
# ═══════════════════════════════════════════════════════════════

def send_email(to: str, subject: str, body: str, html: bool = False,
               attachments: list = None, cc: str = None, bcc: str = None) -> dict:
    """
    Send a real email via SMTP.
    
    Credentials needed (stored as 'email'):
    {
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "username": "layla@makes.studio",
        "password": "app-specific-password"
    }
    """
    creds = get_platform_credential("email")
    if not creds:
        return {"error": "Email not connected. Configure SMTP credentials first."}
    
    try:
        msg = MIMEMultipart()
        msg["From"] = creds["username"]
        msg["To"] = to
        msg["Subject"] = subject
        if cc:
            msg["Cc"] = cc
        if bcc:
            msg["Bcc"] = bcc
        
        if html:
            msg.attach(MIMEText(body, "html"))
        else:
            msg.attach(MIMEText(body, "plain"))
        
        # Add attachments
        if attachments:
            for filepath in attachments:
                with open(filepath, "rb") as f:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(filepath)}")
                    msg.attach(part)
        
        # Send
        context = ssl.create_default_context()
        with smtplib.SMTP(creds["smtp_server"], creds["smtp_port"]) as server:
            server.starttls(context=context)
            server.login(creds["username"], creds["password"])
            recipients = [to]
            if cc:
                recipients.extend(cc.split(","))
            if bcc:
                recipients.extend(bcc.split(","))
            server.sendmail(creds["username"], recipients, msg.as_string())
        
        log_platform_action("email", "send", "success", f"Sent '{subject}' to {to}")
        return {"status": "sent", "to": to, "subject": subject}
    
    except Exception as e:
        log_platform_action("email", "send", "failed", str(e))
        return {"error": f"Failed to send email: {str(e)}"}


# ═══════════════════════════════════════════════════════════════
#  INSTAGRAM Connector (instagrapi)
# ═══════════════════════════════════════════════════════════════

_instagram_client = None

def _get_instagram_client():
    """Get or create Instagram client."""
    global _instagram_client
    if _instagram_client:
        return _instagram_client
    
    creds = get_platform_credential("instagram")
    if not creds:
        return None
    
    from instagrapi import Client
    cl = Client()
    
    # Try to load session
    session_file = os.path.join(os.path.dirname(__file__), f".ig_session_{creds['username']}")
    if os.path.exists(session_file):
        cl.load_settings(session_file)
    
    try:
        cl.login(creds["username"], creds["password"])
        cl.dump_settings(session_file)
        _instagram_client = cl
        return cl
    except Exception as e:
        logger.error(f"Instagram login failed: {e}")
        return None


def instagram_post_photo(image_path: str, caption: str, agent_name: str = None) -> dict:
    """Post a photo to Instagram feed."""
    cl = _get_instagram_client()
    if not cl:
        return {"error": "Instagram not connected. Configure credentials first."}
    
    try:
        media = cl.photo_upload(image_path, caption)
        log_platform_action("instagram", "post_photo", "success",
                           f"Posted photo: {media.pk}", agent_name=agent_name)
        return {
            "status": "posted",
            "media_id": media.pk,
            "url": f"https://instagram.com/p/{media.code}",
        }
    except Exception as e:
        log_platform_action("instagram", "post_photo", "failed", str(e), agent_name=agent_name)
        return {"error": f"Failed to post: {str(e)}"}


def instagram_post_reel(video_path: str, caption: str, agent_name: str = None) -> dict:
    """Post a reel to Instagram."""
    cl = _get_instagram_client()
    if not cl:
        return {"error": "Instagram not connected."}
    
    try:
        media = cl.clip_upload(video_path, caption)
        log_platform_action("instagram", "post_reel", "success",
                           f"Posted reel: {media.pk}", agent_name=agent_name)
        return {
            "status": "posted",
            "media_id": media.pk,
            "url": f"https://instagram.com/reel/{media.code}",
        }
    except Exception as e:
        log_platform_action("instagram", "post_reel", "failed", str(e), agent_name=agent_name)
        return {"error": f"Failed to post reel: {str(e)}"}


def instagram_post_story(image_or_video_path: str, agent_name: str = None) -> dict:
    """Post a story to Instagram."""
    cl = _get_instagram_client()
    if not cl:
        return {"error": "Instagram not connected."}
    
    try:
        if image_or_video_path.endswith(('.mp4', '.mov')):
            media = cl.video_upload_to_story(image_or_video_path)
        else:
            media = cl.photo_upload_to_story(image_or_video_path)
        log_platform_action("instagram", "post_story", "success",
                           f"Posted story: {media.pk}", agent_name=agent_name)
        return {"status": "posted", "media_id": media.pk}
    except Exception as e:
        log_platform_action("instagram", "post_story", "failed", str(e), agent_name=agent_name)
        return {"error": f"Failed to post story: {str(e)}"}


def instagram_get_insights(media_id: str = None, agent_name: str = None) -> dict:
    """Get Instagram analytics/insights."""
    cl = _get_instagram_client()
    if not cl:
        return {"error": "Instagram not connected."}
    
    try:
        user_id = cl.user_id
        insights = cl.insights_media_user(user_id)
        log_platform_action("instagram", "get_insights", "success",
                           "Retrieved insights", agent_name=agent_name)
        return {"status": "success", "insights": str(insights)[:2000]}
    except Exception as e:
        log_platform_action("instagram", "get_insights", "failed", str(e), agent_name=agent_name)
        return {"error": f"Failed to get insights: {str(e)}"}


def instagram_send_dm(username: str, message: str, agent_name: str = None) -> dict:
    """Send a direct message on Instagram."""
    cl = _get_instagram_client()
    if not cl:
        return {"error": "Instagram not connected."}
    
    try:
        user_id = cl.user_id_from_username(username)
        cl.direct_send(message, [user_id])
        log_platform_action("instagram", "send_dm", "success",
                           f"Sent DM to @{username}", agent_name=agent_name)
        return {"status": "sent", "to": username}
    except Exception as e:
        log_platform_action("instagram", "send_dm", "failed", str(e), agent_name=agent_name)
        return {"error": f"Failed to send DM: {str(e)}"}


# ═══════════════════════════════════════════════════════════════
#  YOUTUBE Connector (YouTube Data API v3)
# ═══════════════════════════════════════════════════════════════

def _get_youtube_client():
    """Get YouTube API client."""
    creds = get_platform_credential("youtube")
    if not creds:
        return None
    
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        
        credentials = Credentials(
            token=creds.get("access_token"),
            refresh_token=creds.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=creds.get("client_id"),
            client_secret=creds.get("client_secret"),
            scopes=["https://www.googleapis.com/auth/youtube"]
        )
        youtube = build("youtube", "v3", credentials=credentials)
        return youtube
    except Exception as e:
        logger.error(f"YouTube client creation failed: {e}")
        return None


def youtube_upload_video(video_path: str, title: str, description: str,
                          tags: list = None, privacy: str = "public",
                          agent_name: str = None) -> dict:
    """
    Upload a video to YouTube.
    privacy: public | unlisted | private
    """
    youtube = _get_youtube_client()
    if not youtube:
        return {"error": "YouTube not connected. Configure OAuth credentials first."}
    
    try:
        from googleapiclient.http import MediaFileUpload
        
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags or [],
                "categoryId": "22",  # People & Blogs
            },
            "status": {
                "privacyStatus": privacy,
                "selfDeclaredMadeForKids": False,
            }
        }
        
        media = MediaFileUpload(video_path, mimetype="video/*", resumable=True)
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        response = request.execute()
        
        video_id = response["id"]
        log_platform_action("youtube", "upload_video", "success",
                           f"Uploaded: {video_id}", agent_name=agent_name)
        return {
            "status": "uploaded",
            "video_id": video_id,
            "url": f"https://youtube.com/watch?v={video_id}",
        }
    except Exception as e:
        log_platform_action("youtube", "upload_video", "failed", str(e), agent_name=agent_name)
        return {"error": f"Failed to upload: {str(e)}"}


def youtube_get_analytics(agent_name: str = None) -> dict:
    """Get YouTube channel analytics."""
    youtube = _get_youtube_client()
    if not youtube:
        return {"error": "YouTube not connected."}
    
    try:
        # Get channel stats
        channels = youtube.channels().list(part="statistics,snippet", mine=True).execute()
        if channels["items"]:
            stats = channels["items"][0]["statistics"]
            log_platform_action("youtube", "get_analytics", "success",
                               "Retrieved analytics", agent_name=agent_name)
            return {
                "status": "success",
                "subscribers": int(stats.get("subscriberCount", 0)),
                "total_views": int(stats.get("viewCount", 0)),
                "total_videos": int(stats.get("videoCount", 0)),
            }
        return {"error": "No channel found"}
    except Exception as e:
        log_platform_action("youtube", "get_analytics", "failed", str(e), agent_name=agent_name)
        return {"error": f"Failed to get analytics: {str(e)}"}


def youtube_reply_comment(comment_id: str, text: str, agent_name: str = None) -> dict:
    """Reply to a YouTube comment."""
    youtube = _get_youtube_client()
    if not youtube:
        return {"error": "YouTube not connected."}
    
    try:
        request = youtube.comments().insert(
            part="snippet",
            body={"snippet": {"parentId": comment_id, "textOriginal": text}}
        )
        response = request.execute()
        log_platform_action("youtube", "reply_comment", "success",
                           f"Replied to {comment_id}", agent_name=agent_name)
        return {"status": "replied", "comment_id": response["id"]}
    except Exception as e:
        log_platform_action("youtube", "reply_comment", "failed", str(e), agent_name=agent_name)
        return {"error": f"Failed to reply: {str(e)}"}


# ═══════════════════════════════════════════════════════════════
#  STRIPE Connector (Payments)
# ═══════════════════════════════════════════════════════════════

def _get_stripe_client():
    """Get Stripe client."""
    creds = get_platform_credential("stripe")
    if not creds:
        return None
    
    import stripe
    stripe.api_key = creds["secret_key"]
    return stripe


def stripe_create_invoice(customer_email: str, amount: float, currency: str = "usd",
                          description: str = "", agent_name: str = None) -> dict:
    """Create a real Stripe invoice."""
    stripe = _get_stripe_client()
    if not stripe:
        return {"error": "Stripe not connected. Configure API key first."}
    
    try:
        # Create or find customer
        customers = stripe.Customer.list(email=customer_email, limit=1)
        if customers.data:
            customer = customers.data[0]
        else:
            customer = stripe.Customer.create(email=customer_email)
        
        # Create invoice
        invoice = stripe.Invoice.create(
            customer=customer.id,
            description=description,
            collection_method="send_invoice",
            days_until_due=7,
        )
        
        # Add invoice item
        stripe.InvoiceItem.create(
            customer=customer.id,
            amount=int(amount * 100),  # cents
            currency=currency,
            description=description,
            invoice=invoice.id,
        )
        
        # Finalize and send
        invoice = stripe.Invoice.finalize_invoice(invoice.id)
        invoice = stripe.Invoice.send_invoice(invoice.id)
        
        log_platform_action("stripe", "create_invoice", "success",
                           f"Invoice {invoice.id}: ${amount}", agent_name=agent_name)
        return {
            "status": "sent",
            "invoice_id": invoice.id,
            "invoice_url": invoice.hosted_invoice_url,
            "amount": amount,
            "currency": currency,
        }
    except Exception as e:
        log_platform_action("stripe", "create_invoice", "failed", str(e), agent_name=agent_name)
        return {"error": f"Failed to create invoice: {str(e)}"}


def stripe_create_payment_link(amount: float, currency: str = "usd",
                                product_name: str = "", agent_name: str = None) -> dict:
    """Create a Stripe payment link."""
    stripe = _get_stripe_client()
    if not stripe:
        return {"error": "Stripe not connected."}
    
    try:
        # Create product
        product = stripe.Product.create(name=product_name)
        
        # Create price
        price = stripe.Price.create(
            product=product.id,
            unit_amount=int(amount * 100),
            currency=currency,
        )
        
        # Create payment link
        link = stripe.PaymentLink.create(
            line_items=[{"price": price.id, "quantity": 1}],
        )
        
        log_platform_action("stripe", "create_payment_link", "success",
                           f"Payment link for {product_name}", agent_name=agent_name)
        return {
            "status": "created",
            "payment_url": link.url,
            "product_id": product.id,
            "price_id": price.id,
        }
    except Exception as e:
        log_platform_action("stripe", "create_payment_link", "failed", str(e), agent_name=agent_name)
        return {"error": f"Failed to create payment link: {str(e)}"}


def stripe_check_payment_status(invoice_id: str, agent_name: str = None) -> dict:
    """Check Stripe payment status."""
    stripe = _get_stripe_client()
    if not stripe:
        return {"error": "Stripe not connected."}
    
    try:
        invoice = stripe.Invoice.retrieve(invoice_id)
        log_platform_action("stripe", "check_payment", "success",
                           f"Invoice {invoice_id}: {invoice.status}", agent_name=agent_name)
        return {
            "status": invoice.status,  # paid | open | void
            "amount_paid": invoice.amount_paid / 100 if invoice.amount_paid else 0,
            "invoice_id": invoice_id,
        }
    except Exception as e:
        log_platform_action("stripe", "check_payment", "failed", str(e), agent_name=agent_name)
        return {"error": f"Failed to check payment: {str(e)}"}


# ═══════════════════════════════════════════════════════════════
#  TWITTER/X Connector
# ═══════════════════════════════════════════════════════════════

def _get_twitter_client():
    """Get Twitter client."""
    creds = get_platform_credential("twitter")
    if not creds:
        return None
    
    import tweepy
    client = tweepy.Client(
        consumer_key=creds["consumer_key"],
        consumer_secret=creds["consumer_secret"],
        access_token=creds["access_token"],
        access_token_secret=creds["access_token_secret"],
    )
    return client


def twitter_post_tweet(text: str, agent_name: str = None) -> dict:
    """Post a tweet."""
    client = _get_twitter_client()
    if not client:
        return {"error": "Twitter not connected. Configure API credentials first."}
    
    try:
        response = client.create_tweet(text=text)
        tweet_id = response.data["id"]
        log_platform_action("twitter", "post_tweet", "success",
                           f"Tweet {tweet_id}", agent_name=agent_name)
        return {
            "status": "posted",
            "tweet_id": tweet_id,
            "url": f"https://twitter.com/i/web/status/{tweet_id}",
        }
    except Exception as e:
        log_platform_action("twitter", "post_tweet", "failed", str(e), agent_name=agent_name)
        return {"error": f"Failed to tweet: {str(e)}"}


def twitter_post_thread(tweets: list, agent_name: str = None) -> dict:
    """Post a Twitter thread."""
    client = _get_twitter_client()
    if not client:
        return {"error": "Twitter not connected."}
    
    try:
        tweet_ids = []
        previous_id = None
        for tweet_text in tweets:
            response = client.create_tweet(text=tweet_text, in_reply_to_tweet_id=previous_id)
            tweet_id = response.data["id"]
            tweet_ids.append(tweet_id)
            previous_id = tweet_id
        
        log_platform_action("twitter", "post_thread", "success",
                           f"Thread of {len(tweet_ids)} tweets", agent_name=agent_name)
        return {
            "status": "posted",
            "tweet_ids": tweet_ids,
            "url": f"https://twitter.com/i/web/status/{tweet_ids[0]}",
        }
    except Exception as e:
        log_platform_action("twitter", "post_thread", "failed", str(e), agent_name=agent_name)
        return {"error": f"Failed to post thread: {str(e)}"}


# ═══════════════════════════════════════════════════════════════
#  SLACK/DISCORD Notifications
# ═══════════════════════════════════════════════════════════════

def send_slack_notification(channel: str, message: str, agent_name: str = None) -> dict:
    """Send a Slack notification via webhook."""
    creds = get_platform_credential("slack")
    if not creds:
        return {"error": "Slack not connected. Configure webhook URL first."}
    
    try:
        import httpx
        webhook_url = creds["webhook_url"]
        payload = {"text": message, "channel": channel}
        async def _send():
            async with httpx.AsyncClient() as client:
                resp = await client.post(webhook_url, json=payload)
                return resp.status_code == 200
        success = asyncio.run(_send())
        if success:
            log_platform_action("slack", "notify", "success",
                               f"Sent to {channel}", agent_name=agent_name)
            return {"status": "sent", "channel": channel}
        return {"error": "Slack webhook returned error"}
    except Exception as e:
        log_platform_action("slack", "notify", "failed", str(e), agent_name=agent_name)
        return {"error": f"Failed to send Slack notification: {str(e)}"}


def send_discord_notification(webhook_url: str, message: str, agent_name: str = None) -> dict:
    """Send a Discord notification via webhook."""
    try:
        import httpx
        payload = {"content": message}
        async def _send():
            async with httpx.AsyncClient() as client:
                resp = await client.post(webhook_url, json=payload)
                return resp.status_code == 204
        success = asyncio.run(_send())
        if success:
            log_platform_action("discord", "notify", "success",
                               "Sent Discord notification", agent_name=agent_name)
            return {"status": "sent"}
        return {"error": "Discord webhook returned error"}
    except Exception as e:
        log_platform_action("discord", "notify", "failed", str(e), agent_name=agent_name)
        return {"error": f"Failed to send Discord notification: {str(e)}"}


def send_telegram_notification(bot_token: str, chat_id: str, message: str,
                               agent_name: str = None) -> dict:
    """Send a Telegram notification via bot."""
    try:
        import httpx
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
        async def _send():
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload)
                return resp.json()
        result = asyncio.run(_send())
        if result.get("ok"):
            log_platform_action("telegram", "notify", "success",
                               f"Sent to {chat_id}", agent_name=agent_name)
            return {"status": "sent", "chat_id": chat_id}
        return {"error": result.get("description", "Telegram error")}
    except Exception as e:
        log_platform_action("telegram", "notify", "failed", str(e), agent_name=agent_name)
        return {"error": f"Failed to send Telegram notification: {str(e)}"}


# ═══════════════════════════════════════════════════════════════
#  CALENDAR (ICS)
# ═══════════════════════════════════════════════════════════════

def create_calendar_event(title: str, start_time: str, end_time: str = None,
                           description: str = "", location: str = "",
                           agent_name: str = None) -> dict:
    """Create a calendar event (.ics file)."""
    try:
        from icalendar import Calendar, Event, vText
        from datetime import datetime as dt
        
        cal = Calendar()
        cal.add("prodid", "-//CreatorForge OS//creatorforge.os//")
        cal.add("version", "2.0")
        
        event = Event()
        event.add("summary", title)
        event.add("dtstart", dt.fromisoformat(start_time))
        if end_time:
            event.add("dtend", dt.fromisoformat(end_time))
        else:
            event.add("dtend", dt.fromisoformat(start_time) + timedelta(hours=1))
        if description:
            event.add("description", description)
        if location:
            event.add("location", location)
        event.add("uid", f"creatorforge-{datetime.now().timestamp()}@creatorforge.os")
        
        cal.add_component(event)
        
        # Save .ics file
        ics_path = os.path.join(os.path.dirname(__file__), "documents", f"event_{int(datetime.now().timestamp())}.ics")
        os.makedirs(os.path.dirname(ics_path), exist_ok=True)
        with open(ics_path, "wb") as f:
            f.write(cal.to_ical())
        
        log_platform_action("calendar", "create_event", "success",
                           f"Event: {title}", agent_name=agent_name)
        return {
            "status": "created",
            "ics_path": ics_path,
            "title": title,
            "start": start_time,
        }
    except Exception as e:
        log_platform_action("calendar", "create_event", "failed", str(e), agent_name=agent_name)
        return {"error": f"Failed to create event: {str(e)}"}


# ═══════════════════════════════════════════════════════════════
#  GITHUB Connector
# ═══════════════════════════════════════════════════════════════

def _get_github_client():
    """Get GitHub client."""
    creds = get_platform_credential("github")
    if not creds:
        return None
    
    from github import Github
    return Github(creds["token"])


def github_create_issue(repo: str, title: str, body: str, labels: list = None,
                         agent_name: str = None) -> dict:
    """Create a GitHub issue."""
    g = _get_github_client()
    if not g:
        return {"error": "GitHub not connected. Configure token first."}
    
    try:
        repo_obj = g.get_repo(repo)
        issue = repo_obj.create_issue(title=title, body=body, labels=labels or [])
        log_platform_action("github", "create_issue", "success",
                           f"Issue #{issue.number}: {title}", agent_name=agent_name)
        return {
            "status": "created",
            "issue_number": issue.number,
            "url": issue.html_url,
        }
    except Exception as e:
        log_platform_action("github", "create_issue", "failed", str(e), agent_name=agent_name)
        return {"error": f"Failed to create issue: {str(e)}"}


# ═══════════════════════════════════════════════════════════════
#  Connector Registry
# ═══════════════════════════════════════════════════════════════

CONNECTOR_INFO = {
    "instagram": {
        "display": "Instagram",
        "icon": "📸",
        "description": "Post photos, reels, stories. Send DMs. Get insights.",
        "credential_fields": ["username", "password"],
        "credential_help": "Your Instagram username and password. Use an app-specific password if 2FA is enabled.",
    },
    "youtube": {
        "display": "YouTube",
        "icon": "📺",
        "description": "Upload videos. Get channel analytics. Reply to comments.",
        "credential_fields": ["client_id", "client_secret", "access_token", "refresh_token"],
        "credential_help": "OAuth2 credentials from Google Cloud Console. Enable YouTube Data API v3.",
    },
    "email": {
        "display": "Email (SMTP)",
        "icon": "📧",
        "description": "Send real emails to brands, clients, partners.",
        "credential_fields": ["smtp_server", "smtp_port", "username", "password"],
        "credential_help": "SMTP server details. For Gmail: smtp.gmail.com, port 587, use app-specific password.",
    },
    "stripe": {
        "display": "Stripe",
        "icon": "💳",
        "description": "Create real invoices, payment links, track payments.",
        "credential_fields": ["secret_key"],
        "credential_help": "Stripe secret key (sk_...). Get from dashboard.stripe.com/apikeys.",
    },
    "twitter": {
        "display": "Twitter/X",
        "icon": "🐦",
        "description": "Post tweets and threads.",
        "credential_fields": ["consumer_key", "consumer_secret", "access_token", "access_token_secret"],
        "credential_help": "Twitter API v2 credentials from developer.x.com.",
    },
    "slack": {
        "display": "Slack",
        "icon": "💬",
        "description": "Send notifications to Slack channels.",
        "credential_fields": ["webhook_url"],
        "credential_help": "Slack incoming webhook URL from api.slack.com/messaging/webhooks.",
    },
    "github": {
        "display": "GitHub",
        "icon": "🐙",
        "description": "Create issues, manage repos, track projects.",
        "credential_fields": ["token"],
        "credential_help": "GitHub personal access token from github.com/settings/tokens.",
    },
    "telegram": {
        "display": "Telegram",
        "icon": "✈️",
        "description": "Send notifications via Telegram bot.",
        "credential_fields": ["bot_token", "chat_id"],
        "credential_help": "Bot token from @BotFather, chat ID from your chat.",
    },
}


def get_connector_status() -> list:
    """Get status of all connectors."""
    connected = {p["platform"]: p for p in get_connected_platforms() if p["status"] == "connected"}
    result = []
    for platform, info in CONNECTOR_INFO.items():
        result.append({
            "platform": platform,
            "display": info["display"],
            "icon": info["icon"],
            "description": info["description"],
            "connected": platform in connected,
            "connected_since": connected.get(platform, {}).get("created_at"),
        })
    return result
