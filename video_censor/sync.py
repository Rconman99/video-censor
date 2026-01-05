"""
User Preference Sync Module

Handles synchronization of custom wordlists and presets using Supabase.
"""

import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


import asyncio
from concurrent.futures import ThreadPoolExecutor

@dataclass
class SyncResult:
    """Result of a sync operation."""
    success: bool
    message: str = ""
    items_pushed: int = 0
    items_pulled: int = 0


class SyncManager:
    """
    Manages synchronization of user preferences with Supabase (Async).
    
    Wraps synchronous Supabase client calls in a thread pool executor
    to prevent blocking the main UI loop.
    """
    
    def __init__(self, supabase_url: str, supabase_key: str, user_id: str):
        self.url = supabase_url
        self.key = supabase_key
        self.user_id = user_id
        self._client = None
        self._executor = ThreadPoolExecutor(max_workers=2)
    
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

    async def _run_async(self, func, *args):
        """Helper to run sync functions in executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, func, *args)

    async def push_wordlist(self, words: List[str]) -> bool:
        """Push custom wordlist to cloud (Async)."""
        if not self.is_configured: return False
        
        def _do_push():
            try:
                if not self.client: return False
                data = {
                    "user_id": self.user_id,
                    "words": list(set(words)),
                    "updated_at": datetime.now().isoformat()
                }
                self.client.table("user_wordlists").upsert(data).execute()
                logger.info(f"Pushed {len(words)} words to cloud")
                return True
            except Exception as e:
                logger.error(f"Failed to push wordlist: {e}")
                return False
                
        return await self._run_async(_do_push)

    async def pull_wordlist(self) -> Optional[List[str]]:
        """Pull custom wordlist from cloud (Async)."""
        if not self.is_configured: return None
        
        def _do_pull():
            try:
                if not self.client: return None
                response = self.client.table("user_wordlists").select("words").eq("user_id", self.user_id).execute()
                if response.data and len(response.data) > 0:
                    return response.data[0].get("words", [])
                return []
            except Exception as e:
                logger.error(f"Failed to pull wordlist: {e}")
                return None
                
        return await self._run_async(_do_pull)

    async def push_presets(self, presets: List[Dict[str, Any]]) -> bool:
        """Push all custom presets to cloud (Async)."""
        if not self.is_configured: return False
        
        def _do_push():
            try:
                if not self.client: return False
                success_count = 0
                for preset in presets:
                    data = {
                        "user_id": self.user_id,
                        "name": preset.get("name"),
                        "settings": preset.get("settings", {}),
                        "updated_at": datetime.now().isoformat()
                    }
                    # Upsert using unique constraint (user_id, name)
                    self.client.table("user_presets").upsert(
                        data, on_conflict="user_id,name"
                    ).execute()
                    success_count += 1
                logger.info(f"Pushed {success_count} presets to cloud")
                return True
            except Exception as e:
                logger.error(f"Failed to push presets: {e}")
                return False
                
        return await self._run_async(_do_push)

    async def pull_presets(self) -> Optional[List[Dict[str, Any]]]:
        """Pull all presets for user from cloud (Async)."""
        if not self.is_configured: return None
        
        def _do_pull():
            try:
                if not self.client: return None
                response = self.client.table("user_presets").select("*").eq("user_id", self.user_id).execute()
                presets = []
                if response.data:
                    for record in response.data:
                        presets.append({
                            "name": record["name"],
                            "settings": record["settings"]
                        })
                return presets
            except Exception as e:
                logger.error(f"Failed to pull presets: {e}")
                return None
                
        return await self._run_async(_do_pull)

    async def push_settings(self, config_dict: Dict[str, Any]) -> bool:
        """Push user preferences settings (Async)."""
        if not self.is_configured: return False
        
        def _do_push():
            try:
                if not self.client: return False
                # Filter system/sensitive
                settings_to_sync = {
                    k: v for k, v in config_dict.items() 
                    if k not in ['system', 'sync', 'logging']
                }
                
                data = {
                    "user_id": self.user_id,
                    "settings": settings_to_sync,
                    "updated_at": datetime.now().isoformat()
                }
                self.client.table("user_settings").upsert(data).execute()
                logger.info("Pushed user settings to cloud")
                return True
            except Exception as e:
                logger.error(f"Failed to push settings: {e}")
                return False
                
        return await self._run_async(_do_push)

    async def pull_settings(self) -> Optional[Dict[str, Any]]:
        """Pull user settings from cloud (Async)."""
        if not self.is_configured: return None
        
        def _do_pull():
            try:
                if not self.client: return None
                response = self.client.table("user_settings").select("settings").eq("user_id", self.user_id).execute()
                if response.data and len(response.data) > 0:
                    return response.data[0].get("settings", {})
                return None
            except Exception as e:
                logger.error(f"Failed to pull settings: {e}")
                return None
                
        return await self._run_async(_do_pull)

    async def sync_all(self, local_words: List[str], local_presets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Perform a full sync operation.
        
        Strategy:
        1. Wordlist: Union of Local + Remote
        2. Presets: Pull remote, merge with local (Last Write Wins handled by updated_at if we tracked it, but for now simple overwrite/union)
        
        Returns a dict containing 'words' and 'presets' to update locally.
        """
        result = {
            'words': None,
            'presets': None,
            'success': False
        }
        
        # Parallel fetch
        remote_words_future = self.pull_wordlist()
        remote_presets_future = self.pull_presets()
        
        remote_words, remote_presets = await asyncio.gather(remote_words_future, remote_presets_future)
        
        # Collect push tasks
        push_tasks = []

        # 1. Wordlist Conflict Resolution: Union
        if remote_words is not None:
            merged_words = list(set(local_words) | set(remote_words))
            result['words'] = merged_words
            
            # If local had new words, push the merged set
            if len(merged_words) > len(remote_words):
                push_tasks.append(self.push_wordlist(merged_words))
        
        # 2. Presets Conflict Resolution: Basic Merge
        # We trust remote for existing names, but keep local-only ones
        if remote_presets is not None:
            merged_presets = {p['name']: p for p in local_presets} # Name -> Preset map
            
            # Apply remote (overwriting local if name conflicts)
            # Alternatively: Check timestamps? We don't have local timestamps.
            # Let's assume Cloud is "truth" for sync pull.
            for rp in remote_presets:
                merged_presets[rp['name']] = rp
            
            result['presets'] = list(merged_presets.values())
            
            # Push back any local ones that weren't on remote
            # (Basically just push everything to be safe)
            push_tasks.append(self.push_presets(list(merged_presets.values())))
            
        # Await all pushes to ensure sync completes
        if push_tasks:
            await asyncio.gather(*push_tasks)
            
        result['success'] = True
        return result
