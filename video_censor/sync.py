"""
User Preference Sync Module

Handles synchronization of custom wordlists and presets using Supabase.
"""

import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class SyncResult:
    """Result of a sync operation."""
    success: bool
    message: str = ""
    items_pushed: int = 0
    items_pulled: int = 0


class SyncManager:
    """
    Manages synchronization of user preferences with Supabase.
    """
    
    def __init__(self, supabase_url: str, supabase_key: str, user_id: str):
        self.url = supabase_url
        self.key = supabase_key
        self.user_id = user_id
        self._client = None
        self._initialized = False
        
    @property
    def client(self):
        """Lazy-load Supabase client."""
        if self._client is None:
            try:
                from supabase import create_client
                if not self.url or not self.key:
                    logger.warning("Sync disabled: Missing Supabase URL or Key")
                    return None
                self._client = create_client(self.url, self.key)
                self._initialized = True
            except ImportError:
                logger.error("Supabase library not installed")
                return None
            except Exception as e:
                logger.error(f"Failed to initialize SyncManager: {e}")
                return None
        return self._client

    @property
    def is_configured(self) -> bool:
        """Check if sync is properly configured."""
        return bool(self.url and self.key and self.user_id)

    def push_wordlist(self, words: List[str]) -> bool:
        """
        Push custom wordlist to cloud.
        Merges with existing by default or overwrites?
        Strategy: Union of local + remote is safest for 'sync',
        but simpler to just overwrite if we assume 'my device is latest'.
        Let's do Upsert with current content.
        """
        if not self.client or not self.is_configured:
            return False
            
        try:
            data = {
                "user_id": self.user_id,
                "words": list(set(words)),  # Ensure unique
                "updated_at": datetime.now().isoformat()
            }
            
            self.client.table("user_wordlists").upsert(data).execute()
            logger.info(f"Pushed {len(words)} words to cloud")
            return True
        except Exception as e:
            logger.error(f"Failed to push wordlist: {e}")
            return False

    def pull_wordlist(self) -> Optional[List[str]]:
        """
        Pull custom wordlist from cloud.
        Returns None if failed or not found.
        """
        if not self.client or not self.is_configured:
            return None
            
        try:
            response = self.client.table("user_wordlists").select("words").eq("user_id", self.user_id).execute()
            if response.data and len(response.data) > 0:
                words = response.data[0].get("words", [])
                logger.info(f"Pulled {len(words)} words from cloud")
                return words
            return []
        except Exception as e:
            logger.error(f"Failed to pull wordlist: {e}")
            return None

    def push_presets(self, presets: List[Dict[str, Any]]) -> bool:
        """
        Push all custom presets to cloud.
        Strategy: Delete all for user and re-insert is simplest for full sync,
        but upsert by ID is better if we track IDs.
        Current system might not have stable IDs for local presets.
        If we just use name as key? Let's assume name is key for now.
        """
        if not self.client or not self.is_configured:
            return False
            
        try:
            # 1. Get existing to match IDs or just upsert by name?
            # Let's just upsert each preset based on (user_id, name) if possible,
            # or clean wipe and insert. Wipe and insert is risky for conflicts.
            # Safe bet: Upsert each preset.
            
            success_count = 0
            for preset in presets:
                data = {
                    "user_id": self.user_id,
                    "name": preset.get("name"),
                    "settings": preset.get("settings", {}),
                    "updated_at": datetime.now().isoformat()
                }
                
                # We need a unique constraint on (user_id, name) for UPSERT to work without ID
                # Or we query first.
                existing = self.client.table("user_presets").select("id").eq("user_id", self.user_id).eq("name", preset["name"]).execute()
                
                if existing.data:
                    # Update
                    pid = existing.data[0]["id"]
                    self.client.table("user_presets").update(data).eq("id", pid).execute()
                else:
                    # Insert
                    self.client.table("user_presets").insert(data).execute()
                success_count += 1
                
            logger.info(f"Pushed {success_count} presets to cloud")
            return True
        except Exception as e:
            logger.error(f"Failed to push presets: {e}")
            return False

    def pull_presets(self) -> Optional[List[Dict[str, Any]]]:
        """Pull all presets for user from cloud."""
        if not self.client or not self.is_configured:
            return None
            
        try:
            response = self.client.table("user_presets").select("*").eq("user_id", self.user_id).execute()
            presets = []
            if response.data:
                for record in response.data:
                    presets.append({
                        "name": record["name"],
                        "settings": record["settings"]
                    })
            logger.info(f"Pulled {len(presets)} presets from cloud")
            return presets
        except Exception as e:
            logger.error(f"Failed to pull presets: {e}")
            return None
