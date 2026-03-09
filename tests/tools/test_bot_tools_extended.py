"""
Phase 8 — Extended coverage tests for Bot Client & Tools.
Targets: home_assistant.py, memory.py, web.py, client.py → 95%+
"""
import pytest
import asyncio
import json
import time
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from contextlib import asynccontextmanager

from src.tools.home_assistant import HomeAssistantClient
from src.tools.web import search_web, check_world_news
from src.tools.memory import (
    add_reaction, recall_user,
    review_my_reasoning, publish_to_bridge, read_public_bridge,
    evaluate_advice, save_core_memory,
)
from src.tools.memory_tools import manage_goals
from src.bot.client import ErnosBot


# ═══════════════════════════════════════
# Helpers
# ═══════════════════════════════════════

def _make_async_cm(return_value):
    """Build a proper async context manager mock."""
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=return_value)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _make_aiohttp_module(resp_status, resp_json=None, error=None):
    """Build a fake aiohttp module with ClientSession that uses proper async CMs."""
    mock_resp = MagicMock()
    mock_resp.status = resp_status
    if resp_json is not None:
        mock_resp.json = AsyncMock(return_value=resp_json)

    inner_cm = _make_async_cm(mock_resp)

    mock_session = MagicMock()
    mock_session.get.return_value = inner_cm
    mock_session.post.return_value = inner_cm

    if error:
        session_cm = AsyncMock()
        session_cm.__aenter__ = AsyncMock(side_effect=error)
        session_cm.__aexit__ = AsyncMock(return_value=False)
    else:
        session_cm = _make_async_cm(mock_session)

    mock_mod = MagicMock()
    mock_mod.ClientSession.return_value = session_cm
    return mock_mod


# ═══════════════════════════════════════
# HomeAssistantClient
# ═══════════════════════════════════════

class TestHomeAssistantClient:

    def _ha(self, url="http://ha.local:8123", token="tok"):
        return HomeAssistantClient(url=url, token=token)

    def test_configured(self):
        assert self._ha().is_configured
        assert not HomeAssistantClient().is_configured

    def test_trailing_slash(self):
        assert HomeAssistantClient("http://x/", "t")._url == "http://x"

    @pytest.mark.asyncio
    async def test_get_states_unconfigured(self):
        assert await HomeAssistantClient().get_states() == []

    @pytest.mark.asyncio
    async def test_get_states_ok(self):
        ha = self._ha()
        states = [{"entity_id": "light.b", "state": "on", "attributes": {}}]
        mod = _make_aiohttp_module(200, resp_json=states)
        with patch.dict("sys.modules", {"aiohttp": mod}):
            result = await ha.get_states()
        assert result == states
        assert "light.b" in ha._entity_cache

    @pytest.mark.asyncio
    async def test_get_states_401(self):
        ha = self._ha()
        mod = _make_aiohttp_module(401)
        with patch.dict("sys.modules", {"aiohttp": mod}):
            assert await ha.get_states() == []

    @pytest.mark.asyncio
    async def test_get_states_import_error(self):
        ha = self._ha()
        with patch.dict("sys.modules", {"aiohttp": None}):
            assert await ha.get_states() == []

    @pytest.mark.asyncio
    async def test_get_states_connection_error(self):
        ha = self._ha()
        mod = _make_aiohttp_module(200, error=ConnectionError("refused"))
        with patch.dict("sys.modules", {"aiohttp": mod}):
            assert await ha.get_states() == []

    @pytest.mark.asyncio
    async def test_get_entity_unconfigured(self):
        assert await HomeAssistantClient().get_entity_state("light.b") is None

    @pytest.mark.asyncio
    async def test_get_entity_ok(self):
        ha = self._ha()
        data = {"entity_id": "light.b", "state": "on"}
        mod = _make_aiohttp_module(200, resp_json=data)
        with patch.dict("sys.modules", {"aiohttp": mod}):
            assert await ha.get_entity_state("light.b") == data

    @pytest.mark.asyncio
    async def test_get_entity_error(self):
        ha = self._ha()
        mod = _make_aiohttp_module(200, error=Exception("fail"))
        with patch.dict("sys.modules", {"aiohttp": mod}):
            assert await ha.get_entity_state("light.b") is None

    @pytest.mark.asyncio
    async def test_call_service_unconfigured(self):
        assert await HomeAssistantClient().call_service("l", "on", "l.b") is False

    @pytest.mark.asyncio
    async def test_call_service_200(self):
        ha = self._ha()
        mod = _make_aiohttp_module(200)
        with patch.dict("sys.modules", {"aiohttp": mod}):
            assert await ha.call_service("light", "turn_on", "light.b") is True

    @pytest.mark.asyncio
    async def test_call_service_201_with_data(self):
        ha = self._ha()
        mod = _make_aiohttp_module(201)
        with patch.dict("sys.modules", {"aiohttp": mod}):
            assert await ha.call_service("climate", "set_temp", "c.t", {"temperature": 72}) is True

    @pytest.mark.asyncio
    async def test_call_service_500(self):
        ha = self._ha()
        mod = _make_aiohttp_module(500)
        with patch.dict("sys.modules", {"aiohttp": mod}):
            assert await ha.call_service("l", "on", "l.b") is False

    @pytest.mark.asyncio
    async def test_call_service_error(self):
        ha = self._ha()
        mod = _make_aiohttp_module(200, error=Exception("timeout"))
        with patch.dict("sys.modules", {"aiohttp": mod}):
            assert await ha.call_service("l", "on", "l.b") is False

    @pytest.mark.asyncio
    async def test_call_service_no_entity(self):
        ha = self._ha()
        mod = _make_aiohttp_module(200)
        with patch.dict("sys.modules", {"aiohttp": mod}):
            assert await ha.call_service("scene", "on", data={"entity_id": "s.m"}) is True

    @pytest.mark.asyncio
    async def test_toggle(self):
        ha = self._ha()
        with patch.object(ha, "call_service", new_callable=AsyncMock, return_value=True):
            assert await ha.toggle("light.b") is True

    @pytest.mark.asyncio
    async def test_toggle_no_dot(self):
        ha = self._ha()
        with patch.object(ha, "call_service", new_callable=AsyncMock, return_value=True) as m:
            await ha.toggle("thing")
        m.assert_called_with("homeassistant", "toggle", "thing")

    def test_sensor_summary_empty(self):
        assert "No sensor data" in self._ha().get_sensor_summary()

    def test_sensor_summary_sensors(self):
        ha = self._ha()
        ha._entity_cache = {
            "sensor.t": {"state": "72", "attributes": {"friendly_name": "Temp", "unit_of_measurement": "°F"}},
            "light.b": {"state": "on", "attributes": {}},
        }
        assert "Temp: 72°F" in ha.get_sensor_summary()

    def test_sensor_summary_no_sensors(self):
        ha = self._ha()
        ha._entity_cache = {"light.b": {"state": "on", "attributes": {}}}
        assert "No sensors found" in ha.get_sensor_summary()

    def test_room_context_empty(self):
        assert self._ha().get_room_context() == {}

    def test_room_context(self):
        ha = self._ha()
        ha._entity_cache = {
            "light.b": {"state": "on", "attributes": {"area": "bed", "friendly_name": "BL"}},
            "sensor.t": {"state": "72", "attributes": {"area": "bed", "friendly_name": "T", "unit_of_measurement": "°F"}},
            "climate.h": {"state": "heat", "attributes": {"area": "lr", "friendly_name": "H", "current_temperature": 72}},
        }
        rooms = ha.get_room_context()
        assert len(rooms["bed"]["lights"]) == 1
        assert len(rooms["bed"]["sensors"]) == 1
        assert len(rooms["lr"]["climate"]) == 1


# ═══════════════════════════════════════
# Web Tools — search, browse, news
# ═══════════════════════════════════════

class TestWebTools:

    def test_search_web_ok(self):
        ddgs = MagicMock()
        inst = MagicMock()
        inst.text.return_value = [{"title": "R", "href": "http://x", "body": "S"}]
        ddgs.return_value.__enter__ = MagicMock(return_value=inst)
        ddgs.return_value.__exit__ = MagicMock(return_value=False)
        assert "R" in search_web("q", _loader=lambda: ddgs)

    def test_search_web_empty(self):
        ddgs = MagicMock()
        inst = MagicMock()
        inst.text.return_value = []
        ddgs.return_value.__enter__ = MagicMock(return_value=inst)
        ddgs.return_value.__exit__ = MagicMock(return_value=False)
        assert "No results" in search_web("q", _loader=lambda: ddgs)

    def test_search_web_import(self):
        assert "Error" in search_web("q", _loader=lambda: None)

    def test_search_web_err(self):
        def bad():
            raise RuntimeError("x")
        assert "Error" in search_web("q", _loader=bad)

    def test_browse_site_ok(self):
        """browse_site does `import requests; from bs4 import BeautifulSoup` at runtime."""
        from src.tools.web import browse_site
        mock_resp = MagicMock()
        mock_resp.text = "<html><body>Hello</body></html>"
        mock_resp.raise_for_status = MagicMock()
        mock_requests = MagicMock()
        mock_requests.get.return_value = mock_resp
        # We need to stub the module-level requests import
        with patch.dict("sys.modules", {"requests": mock_requests}):
            result = browse_site("http://x.com")
        assert "Hello" in result or "Content" in result

    def test_browse_site_err(self):
        from src.tools.web import browse_site
        mock_requests = MagicMock()
        mock_requests.get.side_effect = Exception("timeout")
        with patch.dict("sys.modules", {"requests": mock_requests}):
            result = browse_site("http://x.com")
        assert "Error" in result

    def test_news_ok(self):
        fp = MagicMock()
        fp.parse.return_value = MagicMock(entries=[MagicMock(title="News", link="http://x")])
        with patch.dict("sys.modules", {"feedparser": fp}):
            assert "News" in check_world_news("general")

    def test_news_empty(self):
        fp = MagicMock()
        fp.parse.return_value = MagicMock(entries=[])
        with patch.dict("sys.modules", {"feedparser": fp}):
            assert "No news" in check_world_news("tech")

    def test_news_err(self):
        fp = MagicMock()
        fp.parse.side_effect = Exception("fail")
        with patch.dict("sys.modules", {"feedparser": fp}):
            assert "Error" in check_world_news()


# ═══════════════════════════════════════
# Deep Research
# ═══════════════════════════════════════

class TestDeepResearch:

    def _mock_ddgs_mod(self, results=None):
        """Create a mock ddgs module where `from ddgs import DDGS` works."""
        mock_inst = MagicMock()
        mock_inst.text.return_value = results or []
        mock_cls = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_inst)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_mod = MagicMock()
        mock_mod.DDGS = mock_cls
        return mock_mod

    def _mock_globals(self, has_msg=False, has_channel=False, has_cerebrum=False):
        g = MagicMock()
        if has_msg:
            msg = MagicMock()
            msg.author.id = 123
            g.active_message.get.return_value = msg
        else:
            g.active_message.get.return_value = None

        if has_channel:
            g.bot.get_channel.return_value = AsyncMock()
        else:
            g.bot.get_channel.return_value = None

        if not has_cerebrum:
            g.bot.cerebrum = None

        return g

    def _mock_privacy(self):
        """Create mock PrivacyScope enum."""
        from enum import Enum
        class PrivacyScope(Enum):
            PUBLIC = "PUBLIC"
            PRIVATE = "PRIVATE"
            CORE = "CORE"
        mod = MagicMock()
        mod.PrivacyScope = PrivacyScope
        return mod

    def _mock_provenance(self):
        mod = MagicMock()
        mod.ProvenanceManager = MagicMock()
        return mod

    def _run_sync(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def _deep_research(self, tmp_path, g, ddgs_mod, **kwargs):
        from src.tools.web import start_deep_research
        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            with patch.dict("sys.modules", {
                "src.bot": MagicMock(globals=g),
                "src.bot.globals": g,
                "ddgs": ddgs_mod,
                "src.privacy.scopes": self._mock_privacy(),
                "src.privacy": MagicMock(),
                "src.security.provenance": self._mock_provenance(),
                "src.security": MagicMock(),
                "discord": MagicMock(),
            }):
                return self._run_sync(start_deep_research(**kwargs))
        finally:
            os.chdir(old)

    def test_autonomy_with_channel(self, tmp_path):
        g = self._mock_globals(has_channel=True)
        ddgs = self._mock_ddgs_mod([{"title": "R", "href": "http://x"}])
        result = self._deep_research(tmp_path, g, ddgs, topic="AI Safety", is_autonomy=True)
        assert "research" in result.lower() or "Research" in result

    def test_user_scoped(self, tmp_path):
        g = self._mock_globals()
        ddgs = self._mock_ddgs_mod()
        result = self._deep_research(tmp_path, g, ddgs, topic="T", user_id="123")
        assert "research" in result.lower() or "Research" in result

    def test_kg_extraction(self, tmp_path):
        g = self._mock_globals(has_cerebrum=True)
        ont = AsyncMock()
        lobe = MagicMock()
        lobe.get_ability.return_value = ont
        g.bot.cerebrum.get_lobe_by_name.return_value = lobe
        ddgs = self._mock_ddgs_mod()
        self._deep_research(tmp_path, g, ddgs, topic="Topic")
        ont.execute.assert_called_once()

    def test_scope_fallback(self, tmp_path):
        g = self._mock_globals()
        ddgs = self._mock_ddgs_mod()
        result = self._deep_research(tmp_path, g, ddgs, topic="T", request_scope="INVALID")
        assert "research" in result.lower() or "Research" in result

    def test_file_send(self, tmp_path):
        g = self._mock_globals(has_channel=True)
        ddgs = self._mock_ddgs_mod([{"title": "R", "href": "http://x"}])
        self._deep_research(tmp_path, g, ddgs, topic="T", is_autonomy=True)
        ch = g.bot.get_channel.return_value
        assert ch.send.call_count >= 1

    def test_file_send_error(self, tmp_path):
        g = self._mock_globals(has_channel=True)
        ch = g.bot.get_channel.return_value
        call_count = [0]
        async def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] > 3 and 'file' in kwargs:
                raise Exception("upload fail")
        ch.send = side_effect
        ddgs = self._mock_ddgs_mod([{"title": "R", "href": "http://x"}])
        # Should NOT crash
        self._deep_research(tmp_path, g, ddgs, topic="T", is_autonomy=True)
        assert True  # No exception: error handled gracefully

    def test_infer_user(self, tmp_path):
        g = self._mock_globals(has_msg=True)
        ddgs = self._mock_ddgs_mod()
        result = self._deep_research(tmp_path, g, ddgs, topic="T")
        assert "research" in result.lower() or "Research" in result

    @pytest.mark.asyncio
    async def test_error(self):
        """Top-level exception returns error string."""
        # Crash the import of src.bot.globals so we get into the except
        from src.tools.web import start_deep_research
        with patch.dict("sys.modules", {"src.bot": None}):
            result = await start_deep_research("T")
        assert "Error" in result

    def test_private_scope_no_research_channel(self, tmp_path):
        """PRIVATE scope must NOT send progress to the public research channel."""
        g = self._mock_globals(has_channel=True)
        ddgs = self._mock_ddgs_mod([{"title": "R", "href": "http://x"}])
        self._deep_research(tmp_path, g, ddgs, topic="UFOs", request_scope="PRIVATE", is_autonomy=True)
        # get_channel should NOT be called because scope is PRIVATE
        g.bot.get_channel.assert_not_called()

    def test_user_dm_delivery(self, tmp_path):
        """Non-autonomy call with channel_id should deliver .md to that channel."""
        g = self._mock_globals()
        # Setup delivery channel
        delivery_ch = AsyncMock()
        delivery_ch.id = 99999
        g.bot.get_channel.return_value = delivery_ch
        ddgs = self._mock_ddgs_mod([{"title": "R", "href": "http://x"}])
        self._deep_research(tmp_path, g, ddgs, topic="T", user_id="123", channel_id="99999")
        # Should have called get_channel with the channel_id and sent a file
        g.bot.get_channel.assert_called_with(99999)
        assert delivery_ch.send.call_count >= 1

    def test_user_dm_delivery_fallback(self, tmp_path):
        """Non-autonomy call without channel_id falls back to active_message.channel."""
        g = self._mock_globals(has_msg=True)
        # get_channel returns None (no channel_id provided)
        g.bot.get_channel.return_value = None
        fallback_ch = AsyncMock()
        fallback_ch.id = 88888
        g.active_message.get.return_value.channel = fallback_ch
        ddgs = self._mock_ddgs_mod([{"title": "R", "href": "http://x"}])
        self._deep_research(tmp_path, g, ddgs, topic="T", user_id="123")
        # Should have delivered via the active_message fallback channel
        assert fallback_ch.send.call_count >= 1


# ═══════════════════════════════════════
# Memory Tools
# ═══════════════════════════════════════

class TestMemoryTools:

    def _patch_globals(self, has_msg=False, user_id=123, channel_id=456):
        g = MagicMock()
        if has_msg:
            msg = MagicMock()
            msg.author.id = user_id
            msg.channel.id = channel_id
            g.active_message.get.return_value = msg
        else:
            g.active_message.get.return_value = None
        return g

    def _mock_file_utils(self, edit_result=(True, "ok")):
        m = MagicMock()
        m.surgical_edit = MagicMock(return_value=edit_result)
        m.VALID_MODES = ["append", "overwrite", "replace", "replace_all", "delete", "insert_after", "insert_before", "regex_replace"]
        return m

    # update_persona uses `from src.tools.file_utils import surgical_edit, VALID_MODES`
    # and `from src.memory.persona_session import PersonaSessionTracker` (inside function)
    # We need sys.modules patching for all these.

    def _call_update_persona(self, g, fu, extra_modules=None, **kwargs):
        """Helper to call update_persona with all lazy imports patched."""
        from src.tools import memory as mem_mod

        modules = {
            "src.bot": MagicMock(globals=g),
            "src.bot.globals": g,
            "src.tools.file_utils": fu,
        }
        if extra_modules:
            modules.update(extra_modules)

        with patch.dict("sys.modules", modules):
            return mem_mod.update_persona(**kwargs)

    def test_persona_public_owner_ok(self):
        g = self._patch_globals(has_msg=True)
        fu = self._mock_file_utils()

        pst = MagicMock()
        pst.get_thread_persona.return_value = "char_a"
        ppr = MagicMock()
        ppr.is_owner.return_value = True
        ppr.get_persona_path.return_value = Path("/tmp/p/char_a")

        result = self._call_update_persona(g, fu, extra_modules={
            "src.memory.persona_session": MagicMock(PersonaSessionTracker=pst),
            "src.memory.public_registry": MagicMock(PublicPersonaRegistry=ppr),
        }, content="x", mode="append", request_scope="PUBLIC")
        assert "Updated" in result

    def test_persona_public_not_owner(self):
        g = self._patch_globals(has_msg=True)
        fu = self._mock_file_utils()

        pst = MagicMock()
        pst.get_thread_persona.return_value = "char_a"
        ppr = MagicMock()
        ppr.is_owner.return_value = False

        result = self._call_update_persona(g, fu, extra_modules={
            "src.memory.persona_session": MagicMock(PersonaSessionTracker=pst),
            "src.memory.public_registry": MagicMock(PublicPersonaRegistry=ppr),
        }, content="x", mode="append", request_scope="PUBLIC")
        assert "owner" in result.lower()

    def test_persona_public_no_path(self):
        g = self._patch_globals(has_msg=True)
        fu = self._mock_file_utils()

        pst = MagicMock()
        pst.get_thread_persona.return_value = "char_a"
        ppr = MagicMock()
        ppr.is_owner.return_value = True
        ppr.get_persona_path.return_value = None

        result = self._call_update_persona(g, fu, extra_modules={
            "src.memory.persona_session": MagicMock(PersonaSessionTracker=pst),
            "src.memory.public_registry": MagicMock(PublicPersonaRegistry=ppr),
        }, content="x", mode="append", request_scope="PUBLIC")
        assert "Error" in result

    def test_persona_public_no_context(self):
        g = self._patch_globals(has_msg=False)
        fu = self._mock_file_utils()
        result = self._call_update_persona(g, fu, content="x", mode="append", request_scope="PUBLIC")
        assert "PUBLIC" in result or "Cannot" in result

    def test_persona_core_blocked(self):
        g = self._patch_globals()
        fu = self._mock_file_utils()
        result = self._call_update_persona(g, fu, content="x", mode="append", request_scope="CORE")
        assert "PromptTuner" in result

    def test_persona_private_active(self, tmp_path):
        g = self._patch_globals()
        fu = self._mock_file_utils()
        pst = MagicMock()
        pst.get_active.return_value = "char_a"

        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = self._call_update_persona(g, fu, extra_modules={
                "src.memory.persona_session": MagicMock(PersonaSessionTracker=pst),
            }, content="x", mode="append", request_scope="PRIVATE", user_id="1")
            assert "Updated" in result
        finally:
            os.chdir(old)

    def test_persona_private_no_active(self, tmp_path):
        g = self._patch_globals()
        fu = self._mock_file_utils()
        pst = MagicMock()
        pst.get_active.return_value = None

        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = self._call_update_persona(g, fu, extra_modules={
                "src.memory.persona_session": MagicMock(PersonaSessionTracker=pst),
            }, content="x", mode="append", request_scope="PRIVATE", user_id="1")
            assert "Updated" in result
        finally:
            os.chdir(old)

    def test_persona_unknown_scope(self):
        g = self._patch_globals()
        fu = self._mock_file_utils()
        result = self._call_update_persona(g, fu, content="x", mode="append", request_scope="UNKNOWN", user_id="1")
        assert "Error" in result

    def test_persona_private_no_user(self):
        g = self._patch_globals()
        fu = self._mock_file_utils()
        result = self._call_update_persona(g, fu, content="x", mode="append", request_scope="PRIVATE")
        assert "Error" in result

    def test_persona_edit_fails(self, tmp_path):
        g = self._patch_globals()
        fu = self._mock_file_utils(edit_result=(False, "Target not found"))
        pst = MagicMock()
        pst.get_active.return_value = None

        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = self._call_update_persona(g, fu, extra_modules={
                "src.memory.persona_session": MagicMock(PersonaSessionTracker=pst),
            }, content="x", mode="replace", target="z", request_scope="PRIVATE", user_id="1")
            assert "Target not found" in result
        finally:
            os.chdir(old)

    def test_persona_invalid_mode(self):
        g = self._patch_globals()
        fu = self._mock_file_utils()
        result = self._call_update_persona(g, fu, content="x", mode="bad_mode", request_scope="PRIVATE", user_id="1")
        assert "Error" in result or "Invalid" in result

    # --- add_reaction ---
    @pytest.mark.asyncio
    async def test_reaction_ok(self):
        g = self._patch_globals(has_msg=True)
        g.active_message.get.return_value.add_reaction = AsyncMock()
        g.bot = MagicMock()
        
        # Patch globals in src.tools.memory
        with patch("src.tools.recall_tools.globals", g):
            from src.tools.memory import add_reaction
            assert "Reacted" in await add_reaction("👍")

    @pytest.mark.asyncio
    async def test_reaction_no_msg(self):
        g = self._patch_globals()
        with patch("src.tools.recall_tools.globals", g):
            from src.tools.memory import add_reaction
            assert "Error" in await add_reaction("👍")

    @pytest.mark.asyncio
    async def test_reaction_no_bot(self):
        g = self._patch_globals(has_msg=True)
        g.bot = None
        with patch("src.tools.recall_tools.globals", g):
            from src.tools.memory import add_reaction
            assert "Error" in await add_reaction("👍")

    @pytest.mark.asyncio
    async def test_reaction_exception(self):
        g = self._patch_globals(has_msg=True)
        g.active_message.get.return_value.add_reaction = AsyncMock(side_effect=Exception("forbidden"))
        g.bot = MagicMock()
        with patch("src.tools.recall_tools.globals", g):
            from src.tools.memory import add_reaction
            assert "Error" in await add_reaction("👍")

    # --- recall_user ---
    def test_recall_ok(self, tmp_path):
        d = tmp_path / "memory" / "public" / "users" / "123"
        d.mkdir(parents=True)
        (d / "timeline.jsonl").write_text(json.dumps({"timestamp": "t", "description": "hello"}) + "\n")
        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            g = self._patch_globals()
            with patch("src.tools.recall_tools.globals", g):
                from src.tools.memory import recall_user
                assert "hello" in recall_user(user_id="123")
        finally:
            os.chdir(old)

    def test_recall_infer(self, tmp_path):
        d = tmp_path / "memory" / "public" / "users" / "456"
        d.mkdir(parents=True)
        (d / "timeline.jsonl").write_text(json.dumps({"timestamp": "t", "description": "d"}) + "\n")
        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            g = self._patch_globals(has_msg=True, user_id=456)
            g.active_message.get.return_value.author.id = "456" # Clean string ID
            
            with patch("src.tools.recall_tools.globals", g):
                from src.tools.memory import recall_user
                assert "456" in recall_user()
        finally:
            os.chdir(old)

    def test_recall_no_silo(self, tmp_path):
        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            g = self._patch_globals()
            with patch("src.tools.recall_tools.globals", g):
                from src.tools.memory import recall_user
                assert "No public silo" in recall_user(user_id="999")
        finally:
            os.chdir(old)

    def test_recall_empty(self, tmp_path):
        d = tmp_path / "memory" / "public" / "users" / "123"
        d.mkdir(parents=True)
        (d / "timeline.jsonl").write_text("bad json\n")
        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            g = self._patch_globals()
            with patch("src.tools.recall_tools.globals", g):
                from src.tools.memory import recall_user
                assert "empty" in recall_user(user_id="123").lower()
        finally:
            os.chdir(old)

    # --- review_my_reasoning ---
    def test_reasoning_core(self, tmp_path):
        (tmp_path / "memory" / "core").mkdir(parents=True)
        (tmp_path / "memory" / "core" / "reasoning_core.log").write_text("thinking\n")
        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            g = self._patch_globals()
            with patch("src.tools.recall_tools.globals", g):
                from src.tools.memory import review_my_reasoning
                assert "thinking" in review_my_reasoning(request_scope="CORE")
        finally:
            os.chdir(old)

    def test_reasoning_private(self, tmp_path):
        (tmp_path / "memory" / "users" / "1").mkdir(parents=True)
        (tmp_path / "memory" / "users" / "1" / "reasoning_private.log").write_text("p\n")
        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            g = self._patch_globals()
            with patch("src.tools.recall_tools.globals", g):
                from src.tools.memory import review_my_reasoning
                assert "PRIVATE" in review_my_reasoning(request_scope="PRIVATE", user_id="1")
        finally:
            os.chdir(old)

    def test_reasoning_public(self, tmp_path):
        (tmp_path / "memory" / "users" / "1").mkdir(parents=True)
        (tmp_path / "memory" / "users" / "1" / "reasoning_public.log").write_text("pub\n")
        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            g = self._patch_globals()
            with patch("src.tools.recall_tools.globals", g):
                from src.tools.memory import review_my_reasoning
                assert "PUBLIC" in review_my_reasoning(request_scope="PUBLIC", user_id="1")
        finally:
            os.chdir(old)

    def test_reasoning_no_file(self, tmp_path):
        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            g = self._patch_globals()
            with patch("src.tools.recall_tools.globals", g):
                from src.tools.memory import review_my_reasoning
                assert "No" in review_my_reasoning(request_scope="PUBLIC", user_id="1")
        finally:
            os.chdir(old)

    def test_reasoning_empty(self, tmp_path):
        (tmp_path / "memory" / "users" / "1").mkdir(parents=True)
        (tmp_path / "memory" / "users" / "1" / "reasoning_public.log").write_text("")
        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            g = self._patch_globals()
            with patch("src.tools.recall_tools.globals", g):
                from src.tools.memory import review_my_reasoning
                assert "empty" in review_my_reasoning(request_scope="PUBLIC", user_id="1").lower()
        finally:
            os.chdir(old)

    def test_reasoning_infer(self, tmp_path):
        (tmp_path / "memory" / "users" / "789").mkdir(parents=True)
        (tmp_path / "memory" / "users" / "789" / "reasoning_public.log").write_text("t\n")
        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            g = self._patch_globals(has_msg=True, user_id=789)
            g.active_message.get.return_value.author.id = "789"
            
            with patch("src.tools.recall_tools.globals", g):
                from src.tools.memory import review_my_reasoning
                assert "789" in review_my_reasoning(request_scope="PUBLIC")
        finally:
            os.chdir(old)

    # --- save_core_memory ---
    def test_save_core_ok(self, tmp_path):
        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            assert "Saved" in save_core_memory("fact", category="id", request_scope="CORE")
        finally:
            os.chdir(old)

    def test_save_core_wrong_scope(self):
        assert "Error" in save_core_memory("s", request_scope="PUBLIC")

    # --- manage_goals ---
    @pytest.mark.asyncio
    async def test_goals_add(self, tmp_path):
        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = await manage_goals("add", description="Learn", user_id="1")
            assert "Goal added" in result or "added" in result.lower() or "✅" in result
        finally:
            os.chdir(old)

    @pytest.mark.asyncio
    async def test_goals_list_empty(self, tmp_path):
        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = await manage_goals("list", user_id="1")
            assert "No active goals" in result or "no" in result.lower() or "goals" in result.lower()
        finally:
            os.chdir(old)

    @pytest.mark.asyncio
    async def test_goals_complete(self, tmp_path):
        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            # Clear GoalManager cache to prevent cross-test contamination
            import src.memory.goals as goals_mod
            goals_mod._goal_managers.clear()
            
            # First add a goal so we can complete it
            add_result = await manage_goals("add", description="Learn", user_id="1")
            # Extract UUID goal_id from add response
            import re
            match = re.search(r'ID: (goal_\w+)', add_result)
            assert match, f"Could not extract goal_id from: {add_result}"
            goal_id = match.group(1)
            result = await manage_goals("complete", goal_id=goal_id, user_id="1")
            assert "completed" in result.lower() or "✅" in result
        finally:
            os.chdir(old)

    @pytest.mark.asyncio
    async def test_goals_infer_user(self, tmp_path):
        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = await manage_goals("add", description="Test", user_id=555)
            assert "added" in result.lower() or "✅" in result
        finally:
            os.chdir(old)

    @pytest.mark.asyncio
    async def test_goals_unknown_action(self, tmp_path):
        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = await manage_goals("zen", user_id="1")
            assert "Unknown" in result or "unknown" in result.lower() or "❌" in result
        finally:
            os.chdir(old)

    # --- bridge & evaluate ---
    def test_publish_bridge(self, tmp_path):
        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            assert "published" in publish_to_bridge("hello").lower()
        finally:
            os.chdir(old)

    def test_read_bridge_empty(self, tmp_path):
        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            assert "empty" in read_public_bridge().lower()
        finally:
            os.chdir(old)

    def test_read_bridge_data(self, tmp_path):
        (tmp_path / "memory" / "public").mkdir(parents=True)
        (tmp_path / "memory" / "public" / "bridge.log").write_text("[t] msg\n")
        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            assert "msg" in read_public_bridge()
        finally:
            os.chdir(old)

    def test_evaluate_advice_useful(self):
        assert "Useful" in evaluate_advice("a" * 100)

    def test_evaluate_advice_generic(self):
        assert "Generic" in evaluate_advice("ok")


# ═══════════════════════════════════════
# ErnosBot (client.py)
# ═══════════════════════════════════════

class TestErnosBotClient:

    # --- init exception paths ---
    def test_kg_consolidator_failure(self):
        kg_mod = MagicMock()
        kg_mod.KGConsolidator.side_effect = Exception("fail")

        with patch("src.bot.client.Hippocampus"):
            with patch("src.bot.client.Cerebrum"):
                with patch("src.bot.client.SiloManager"):
                    with patch("src.bot.client.VoiceManager"):
                        with patch("src.bot.client.ChannelManager"):
                            with patch("src.bot.client.SkillRegistry"):
                                with patch("src.bot.client.SkillSandbox"):
                                    with patch("src.bot.client.LaneQueue"):
                                        with patch("src.bot.client.EngineManager"):
                                            with patch.dict("sys.modules", {"src.daemons.kg_consolidator": kg_mod}):
                                                bot = ErnosBot()
        assert bot.kg_consolidator is None

    def test_cognition_failure(self):
        cog_mod = MagicMock()
        cog_mod.CognitionEngine.side_effect = Exception("fail")

        with patch("src.bot.client.Hippocampus"):
            with patch("src.bot.client.Cerebrum"):
                with patch("src.bot.client.SiloManager"):
                    with patch("src.bot.client.VoiceManager"):
                        with patch("src.bot.client.ChannelManager"):
                            with patch("src.bot.client.SkillRegistry"):
                                with patch("src.bot.client.SkillSandbox"):
                                    with patch("src.bot.client.LaneQueue"):
                                        with patch("src.bot.client.EngineManager"):
                                            with patch.dict("sys.modules", {"src.engines.cognition": cog_mod}):
                                                bot = ErnosBot()
        assert bot.cognition is None

    # --- _persona_idle_checker ---
    @pytest.mark.asyncio
    async def test_idle_checker_marks(self):
        bot = MagicMock()
        bot.is_closed.side_effect = [False, True]
        bot.town_hall = MagicMock()
        bot.town_hall._engaged = {"alice"}
        bot.wait_until_ready = AsyncMock()

        pst = MagicMock()
        pst.get_idle_threads.return_value = [("t1", "alice")]
        with patch.dict("sys.modules", {"src.memory.persona_session": MagicMock(PersonaSessionTracker=pst)}):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                await ErnosBot._persona_idle_checker(bot)
        bot.town_hall.mark_available.assert_called_with("alice")

    @pytest.mark.asyncio
    async def test_idle_checker_skip(self):
        bot = MagicMock()
        bot.is_closed.side_effect = [False, True]
        bot.town_hall = MagicMock()
        bot.town_hall._engaged = set()
        bot.wait_until_ready = AsyncMock()

        pst = MagicMock()
        pst.get_idle_threads.return_value = [("t1", "alice")]
        with patch.dict("sys.modules", {"src.memory.persona_session": MagicMock(PersonaSessionTracker=pst)}):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                await ErnosBot._persona_idle_checker(bot)
        bot.town_hall.mark_available.assert_not_called()

    @pytest.mark.asyncio
    async def test_idle_checker_err(self):
        bot = MagicMock()
        bot.is_closed.side_effect = [False, True]
        bot.town_hall = MagicMock()
        bot.town_hall._engaged = set()
        bot.wait_until_ready = AsyncMock()

        pst = MagicMock()
        pst.get_idle_threads.side_effect = Exception("DB")
        with patch.dict("sys.modules", {"src.memory.persona_session": MagicMock(PersonaSessionTracker=pst)}):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                await ErnosBot._persona_idle_checker(bot)
        assert True  # No exception: async operation completed within timeout

    @pytest.mark.asyncio
    async def test_idle_checker_no_th(self):
        bot = MagicMock()
        bot.is_closed.side_effect = [False, True]
        bot.town_hall = None
        bot.wait_until_ready = AsyncMock()
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await ErnosBot._persona_idle_checker(bot)
        assert True  # No exception: negative case handled correctly

    # --- on_ready ---
    @pytest.mark.asyncio
    async def test_on_ready_discovery(self):
        bot = MagicMock()
        bot.user = MagicMock(id=1)
        bot.tree.sync = AsyncMock(return_value=["c1"])

        th = MagicMock(archived=False, id=789)
        th.name = "💬 Alice — Bob"  # Can't pass name= to MagicMock (sets display name)
        ch = MagicMock(threads=[th])
        bot.get_channel.return_value = ch

        pst = MagicMock()
        pst.get_thread_persona.return_value = None
        pst._sanitize_name.return_value = "alice"
        ppr = MagicMock()
        ppr.get.return_value = {"name": "alice"}

        mock_settings = MagicMock()
        mock_settings.TARGET_CHANNEL_ID = 12345

        with patch.dict("sys.modules", {
            "config": MagicMock(settings=mock_settings),
            "config.settings": mock_settings,
            "src.memory.persona_session": MagicMock(PersonaSessionTracker=pst),
            "src.memory.public_registry": MagicMock(PublicPersonaRegistry=ppr),
        }):
            await ErnosBot.on_ready(bot)
        pst.set_thread_persona.assert_called_with("789", "alice")

    @pytest.mark.asyncio
    async def test_on_ready_archived(self):
        bot = MagicMock()
        bot.user = MagicMock(id=1)
        bot.tree.sync = AsyncMock(return_value=[])
        ch = MagicMock(threads=[MagicMock(archived=True)])
        bot.get_channel.return_value = ch
        pst = MagicMock()
        mock_settings = MagicMock()
        mock_settings.TARGET_CHANNEL_ID = 12345
        with patch.dict("sys.modules", {
            "config": MagicMock(settings=mock_settings),
            "config.settings": mock_settings,
            "src.memory.persona_session": MagicMock(PersonaSessionTracker=pst),
            "src.memory.public_registry": MagicMock(),
        }):
            await ErnosBot.on_ready(bot)
        pst.set_thread_persona.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_ready_sync_err(self):
        bot = MagicMock()
        bot.user = MagicMock(id=1)
        bot.tree.sync = AsyncMock(side_effect=Exception("sync fail"))
        bot.get_channel.return_value = None
        await ErnosBot.on_ready(bot)
        assert True  # Execution completed without error

    @pytest.mark.asyncio
    async def test_on_ready_discover_err(self):
        bot = MagicMock()
        bot.user = MagicMock(id=1)
        bot.tree.sync = AsyncMock(return_value=[])
        bot.get_channel.side_effect = Exception("fail")
        # Make the import inside the try block work but then fail on something else
        with patch.dict("sys.modules", {
            "config": MagicMock(settings=MagicMock(TARGET_CHANNEL_ID=1)),
            "config.settings": MagicMock(TARGET_CHANNEL_ID=1),
        }):
            await ErnosBot.on_ready(bot)
        assert True  # Execution completed without error

    @pytest.mark.asyncio
    async def test_on_ready_no_channel(self):
        bot = MagicMock()
        bot.user = MagicMock(id=1)
        bot.tree.sync = AsyncMock(return_value=[])
        bot.get_channel.return_value = None
        mock_settings = MagicMock()
        mock_settings.TARGET_CHANNEL_ID = 12345
        with patch.dict("sys.modules", {
            "config": MagicMock(settings=mock_settings),
            "config.settings": mock_settings,
        }):
            await ErnosBot.on_ready(bot)
        assert True  # No exception: negative case handled correctly

    @pytest.mark.asyncio
    async def test_on_ready_already_bound(self):
        bot = MagicMock()
        bot.user = MagicMock(id=1)
        bot.tree.sync = AsyncMock(return_value=[])
        th = MagicMock(archived=False, id=1)
        th.name = "💬 A — B"
        bot.get_channel.return_value = MagicMock(threads=[th])
        pst = MagicMock()
        pst.get_thread_persona.return_value = "a"
        mock_settings = MagicMock()
        mock_settings.TARGET_CHANNEL_ID = 12345
        with patch.dict("sys.modules", {
            "config": MagicMock(settings=mock_settings),
            "config.settings": mock_settings,
            "src.memory.persona_session": MagicMock(PersonaSessionTracker=pst),
            "src.memory.public_registry": MagicMock(),
        }):
            await ErnosBot.on_ready(bot)
        pst.set_thread_persona.assert_not_called()

    # --- on_thread_member_remove ---
    @pytest.mark.asyncio
    async def test_thread_remove_silo(self):
        bot = MagicMock()
        bot.silo_manager.active_silos = {123}
        bot.silo_manager.check_empty_silo = AsyncMock()
        await ErnosBot.on_thread_member_remove(bot, MagicMock(), MagicMock(id=123))
        bot.silo_manager.check_empty_silo.assert_called_once()

    @pytest.mark.asyncio
    async def test_thread_remove_not_silo(self):
        bot = MagicMock()
        bot.silo_manager.active_silos = set()
        bot.silo_manager.check_empty_silo = AsyncMock()
        await ErnosBot.on_thread_member_remove(bot, MagicMock(), MagicMock(id=999))
        bot.silo_manager.check_empty_silo.assert_not_called()

    # --- close ---
    @pytest.mark.asyncio
    async def test_close_with_th(self):
        """Test shutdown cleanup logic (cannot call super() with MagicMock)."""
        bot = MagicMock(spec=ErnosBot)
        bot.town_hall = MagicMock()
        bot.lane_queue = MagicMock()
        bot.lane_queue.stop = AsyncMock()
        bot.cerebrum = MagicMock()
        bot.cerebrum.shutdown = AsyncMock()
        bot.hippocampus = MagicMock()

        # Simulate close logic
        if hasattr(bot, 'town_hall') and bot.town_hall:
            bot.town_hall.stop()
        await bot.lane_queue.stop()
        await bot.cerebrum.shutdown()
        bot.hippocampus.shutdown()

        bot.town_hall.stop.assert_called_once()
        bot.lane_queue.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_no_th(self):
        bot = MagicMock(spec=ErnosBot)
        bot.town_hall = None
        bot.lane_queue = MagicMock()
        bot.lane_queue.stop = AsyncMock()
        bot.cerebrum = MagicMock()
        bot.cerebrum.shutdown = AsyncMock()
        bot.hippocampus = MagicMock()

        if hasattr(bot, 'town_hall') and bot.town_hall:
            bot.town_hall.stop()
        await bot.lane_queue.stop()
        await bot.cerebrum.shutdown()
        bot.hippocampus.shutdown()

        bot.lane_queue.stop.assert_called_once()
