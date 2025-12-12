"""
Push notification helper for Video Censor.
Uses ntfy.sh for free mobile push notifications.
"""

import requests
from typing import Optional
from pathlib import Path


def send_notification(
    topic: str,
    title: str,
    message: str,
    priority: str = "default",
    tags: Optional[list] = None
) -> bool:
    """
    Send a push notification via ntfy.sh.
    
    Args:
        topic: The ntfy topic to publish to (e.g., "videocensor-ryan-12345")
        title: Notification title
        message: Notification body
        priority: "min", "low", "default", "high", "urgent"
        tags: Optional emoji tags like ["white_check_mark", "movie_camera"]
    
    Returns:
        True if notification was sent successfully
    """
    if not topic:
        return False
    
    url = f"https://ntfy.sh/{topic}"
    
    headers = {
        "Title": title,
        "Priority": priority,
    }
    
    if tags:
        headers["Tags"] = ",".join(tags)
    
    try:
        response = requests.post(url, data=message.encode('utf-8'), headers=headers, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Failed to send notification: {e}")
        return False


def notify_video_complete(topic: str, filename: str, duration: str = "") -> bool:
    """Send notification when a video finishes processing."""
    duration_str = f" ({duration})" if duration else ""
    return send_notification(
        topic=topic,
        title="✅ Video Complete",
        message=f"{filename}{duration_str}",
        priority="default",
        tags=["white_check_mark", "movie_camera"]
    )


def notify_video_failed(topic: str, filename: str, error: str = "") -> bool:
    """Send notification when a video fails processing."""
    error_str = f"\n{error[:100]}" if error else ""
    return send_notification(
        topic=topic,
        title="❌ Video Failed",
        message=f"{filename}{error_str}",
        priority="high",
        tags=["x", "warning"]
    )


def notify_batch_complete(topic: str, total: int, successful: int, failed: int) -> bool:
    """Send notification when entire batch is done."""
    status = "🎉 All videos completed!" if failed == 0 else f"⚠️ {failed} video(s) failed"
    return send_notification(
        topic=topic,
        title="📋 Batch Complete",
        message=f"{status}\n{successful}/{total} successful",
        priority="high",
        tags=["tada", "clapper"]
    )


def notify_progress(topic: str, filename: str, progress: int, eta: str) -> bool:
    """Send notification for progress updates (e.g. 50%, 90%)."""
    return send_notification(
        topic=topic,
        title=f"⏳ {progress}% Complete",
        message=f"{filename}\nEst. time remaining: {eta}",
        priority="low",
        tags=["hourglass_flowing_sand"]
    )
