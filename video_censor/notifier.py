"""
Notification manager for Video Censor.

Handles:
- Local macOS notifications via osascript
- Mobile notifications via ntfy.sh
"""

import logging
import requests
import subprocess
from typing import Optional
from .config import Config

logger = logging.getLogger(__name__)


class Notifier:
    def __init__(self, config: Config):
        self.config = config
    
    def send(self, title: str, message: str, priority: str = "default"):
        """Send notification via configured channels."""
        if not self.config.notifications.enabled:
            return
            
        # Desktop notification (macOS)
        try:
            self._send_macos_notification(title, message)
        except Exception as e:
            logger.debug(f"Failed to send macOS notification: {e}")
            
        # Mobile notification (ntfy.sh)
        if self.config.notifications.ntfy_topic:
            try:
                self._send_ntfy_notification(title, message, priority)
            except Exception as e:
                logger.error(f"Failed to send ntfy notification: {e}")
    
    def _send_macos_notification(self, title: str, message: str):
        """Send native macOS notification using osascript."""
        # Sanitize inputs to prevent AppleScript injection
        safe_title = title.replace('\\', '\\\\').replace('"', '\\"')
        safe_message = message.replace('\\', '\\\\').replace('"', '\\"')
        script = f'display notification "{safe_message}" with title "{safe_title}" subtitle "Video Censor"'
        subprocess.run(["osascript", "-e", script], check=False)
    
    def _send_ntfy_notification(self, title: str, message: str, priority: str):
        """Send notification via ntfy.sh."""
        topic = self.config.notifications.ntfy_topic
        url = f"https://ntfy.sh/{topic}"
        
        headers = {
            "Title": title,
            "Tags": "movie_camera"
        }
        
        if priority == "high" or "Error" in title:
            headers["Priority"] = "high"
            headers["Tags"] = "warning"
            
        requests.post(url, data=message.encode('utf-8'), headers=headers, timeout=5)


# Global instance
_notifier: Optional[Notifier] = None

def get_notifier(config: Optional[Config] = None) -> Notifier:
    """Get or create global notifier instance."""
    global _notifier
    if _notifier is None:
        if config is None:
            # Fallback for when config isn't passed (should happen rarely)
            config = Config.load()
        _notifier = Notifier(config)
    return _notifier
