import pytest
import asyncio
from unittest.mock import MagicMock, patch
from video_censor.sync import SyncManager

# Mock pytest-asyncio behavior if not available
def async_test(coro):
    def wrapper(*args, **kwargs):
        return asyncio.run(coro(*args, **kwargs))
    return wrapper

class TestAsyncSync:
    
    def test_sync_manager_init(self):
        manager = SyncManager("http://test.url", "test-key", "user-123")
        assert manager.url == "http://test.url"
        assert manager.key == "test-key"
        assert manager.user_id == "user-123"
        assert not manager._client

    @patch("supabase.create_client")
    def test_auth_validation_async(self, mock_create):
        # We wrap the async call in asyncio.run since we aren't using pytest-asyncio plugin explicitly here to be safe
        async def run_test():
            manager = SyncManager("", "", "")
            assert not await manager.push_wordlist(["test"])
            
            manager = SyncManager("url", "key", "uid")
            # Client creation fails -> False
            mock_create.side_effect = ImportError("No module")
            assert not await manager.push_wordlist(["test"])
            
        asyncio.run(run_test())

    @patch("supabase.create_client")
    def test_push_pull_flow(self, mock_create):
        async def run_test():
            # Setup mock
            mock_client = MagicMock()
            mock_create.return_value = mock_client
            
            # Configure table mocks
            wordlists_table = MagicMock()
            presets_table = MagicMock()
            settings_table = MagicMock()
            
            def get_table_mock(name):
                if name == "user_wordlists": return wordlists_table
                if name == "user_presets": return presets_table
                if name == "user_settings": return settings_table
                return MagicMock()
            
            mock_client.table.side_effect = get_table_mock
            
            manager = SyncManager("url", "key", "uid")
            
            # 1. Test Push Wordlist
            wordlists_table.upsert.return_value.execute.return_value = None
            res = await manager.push_wordlist(["foo", "bar"])
            assert res is True
            # Check call args
            args = wordlists_table.upsert.call_args[0][0]
            assert set(args["words"]) == {"foo", "bar"}
            
            # 2. Test Pull Wordlist
            wordlists_table.select.return_value.eq.return_value.execute.return_value.data = [{"words": ["baz"]}]
            words = await manager.pull_wordlist()
            assert words == ["baz"]
            
            # 3. Test Sync All Strategy
            # Mock pull return for wordlist
            wordlists_table.select.return_value.eq.return_value.execute.return_value.data = [{"words": ["remote"]}]
            # Mock pull return for presets (empty)
            presets_table.select.return_value.eq.return_value.execute.return_value.data = []
            
            res_all = await manager.sync_all(["local"], [])
            
            assert res_all['success'] is True
            assert "local" in res_all['words']
            assert "remote" in res_all['words']
            
            # Verify push was triggered for the union
            # The last upsert call on wordlists_table should be the merged list
            last_push = wordlists_table.upsert.call_args[0][0]
            assert "local" in last_push["words"] and "remote" in last_push["words"]
            
        asyncio.run(run_test())
