"""
Tests for Memory Tools
Targeting 95%+ coverage for src/tools/memory_tools.py
"""
import pytest
from unittest.mock import patch, MagicMock
from src.tools.memory_tools import (
    manage_lessons, 
    manage_preferences, 
    manage_calendar, 
    manage_goals
)


class TestManageLessons:
    """Tests for manage_lessons tool."""
    
    @pytest.mark.asyncio
    async def test_add_lesson_success(self):
        """Test adding a lesson."""
        with patch('src.memory.lessons.LessonManager') as mock_mgr:
            mock_instance = MagicMock()
            mock_instance.add_lesson.return_value = "✅ Lesson added: abc123"
            mock_mgr.return_value = mock_instance
            
            result = await manage_lessons(
                action="add",
                content="Test lesson content",
                user_id=123
            )
            
            assert "abc123" in result or "added" in result.lower()
    
    @pytest.mark.asyncio
    async def test_add_lesson_no_content(self):
        """Test add action without content."""
        result = await manage_lessons(action="add")
        assert "Content required" in result
    
    @pytest.mark.asyncio
    async def test_search_lessons_success(self):
        """Test searching lessons."""
        with patch('src.memory.lessons.LessonManager') as mock_mgr:
            mock_instance = MagicMock()
            mock_instance.search_lessons.return_value = [
                {"id": "1", "content": "Test lesson about Python programming"},
                {"id": "2", "content": "Another lesson about Python"}
            ]
            mock_mgr.return_value = mock_instance
            
            result = await manage_lessons(action="search", query="Python")
            
            assert "Found 2 lessons" in result
    
    @pytest.mark.asyncio
    async def test_search_lessons_no_results(self):
        """Test search with no results."""
        with patch('src.memory.lessons.LessonManager') as mock_mgr:
            mock_instance = MagicMock()
            mock_instance.search_lessons.return_value = []
            mock_mgr.return_value = mock_instance
            
            result = await manage_lessons(action="search", query="nonexistent")
            
            assert "No lessons found" in result
    
    @pytest.mark.asyncio
    async def test_search_no_query(self):
        """Test search without query."""
        result = await manage_lessons(action="search")
        assert "Query required" in result
    
    @pytest.mark.asyncio
    async def test_list_lessons(self):
        """Test listing lessons."""
        with patch('src.memory.lessons.LessonManager') as mock_mgr:
            mock_instance = MagicMock()
            mock_instance.get_all_lessons.return_value = ["Lesson 1", "Lesson 2"]
            mock_mgr.return_value = mock_instance
            
            result = await manage_lessons(action="list")
            
            assert "Active Lessons" in result
    
    @pytest.mark.asyncio
    async def test_list_lessons_empty(self):
        """Test listing when no lessons exist."""
        with patch('src.memory.lessons.LessonManager') as mock_mgr:
            mock_instance = MagicMock()
            mock_instance.get_all_lessons.return_value = []
            mock_mgr.return_value = mock_instance
            
            result = await manage_lessons(action="list")
            
            assert "No lessons found" in result
    
    @pytest.mark.asyncio
    async def test_verify_lesson(self):
        """Test verifying a lesson."""
        with patch('src.memory.lessons.LessonManager') as mock_mgr:
            mock_instance = MagicMock()
            mock_instance.verify_lesson.return_value = "✅ Lesson verified"
            mock_mgr.return_value = mock_instance
            
            result = await manage_lessons(action="verify", lesson_id="abc123")
            
            assert "verified" in result.lower()
    
    @pytest.mark.asyncio
    async def test_verify_no_lesson_id(self):
        """Test verify without lesson_id."""
        result = await manage_lessons(action="verify")
        assert "lesson_id required" in result
    
    @pytest.mark.asyncio
    async def test_reject_lesson(self):
        """Test rejecting a lesson."""
        with patch('src.memory.lessons.LessonManager') as mock_mgr:
            mock_instance = MagicMock()
            mock_instance.reject_lesson.return_value = "✅ Lesson rejected"
            mock_mgr.return_value = mock_instance
            
            result = await manage_lessons(action="reject", lesson_id="abc123")
            
            assert "rejected" in result.lower()
    
    @pytest.mark.asyncio
    async def test_reject_no_lesson_id(self):
        """Test reject without lesson_id."""
        result = await manage_lessons(action="reject")
        assert "lesson_id required" in result
    
    @pytest.mark.asyncio
    async def test_stats(self):
        """Test getting lesson stats."""
        with patch('src.memory.lessons.LessonManager') as mock_mgr:
            mock_instance = MagicMock()
            mock_instance.get_stats.return_value = {
                "core_lessons": 5,
                "user_lessons": 10,
                "total": 15
            }
            mock_mgr.return_value = mock_instance
            
            result = await manage_lessons(action="stats")
            
            assert "5 CORE" in result
            assert "10 USER" in result
    
    @pytest.mark.asyncio
    async def test_unknown_action(self):
        """Test unknown action."""
        result = await manage_lessons(action="invalid")
        assert "Unknown action" in result
    
    @pytest.mark.asyncio
    async def test_exception_handling(self):
        """Test exception handling."""
        with patch('src.memory.lessons.LessonManager') as mock_mgr:
            mock_instance = MagicMock()
            mock_instance.get_all_lessons.side_effect = Exception("Database error")
            mock_mgr.return_value = mock_instance
            
            result = await manage_lessons(action="list")
            
            assert "Error" in result


class TestManagePreferences:
    """Tests for manage_preferences tool."""
    
    @pytest.mark.asyncio
    async def test_no_user_id(self):
        """Test error when no user_id provided."""
        result = await manage_preferences(action="list")
        assert "user_id required" in result
    
    @pytest.mark.asyncio
    async def test_set_preference(self):
        """Test setting a preference."""
        with patch('src.memory.preferences.PreferencesManager') as mock_mgr:
            mock_mgr.update_preference.return_value = "✅ Preference set"
            
            result = await manage_preferences(
                action="set",
                key="theme",
                value="dark",
                user_id=123
            )
            
            assert "set" in result.lower() or "✅" in result
    
    @pytest.mark.asyncio
    async def test_set_preference_missing_args(self):
        """Test set without key/value."""
        result = await manage_preferences(action="set", user_id=123)
        assert "key" in result.lower() and "value" in result.lower()
    
    @pytest.mark.asyncio
    async def test_get_preference(self):
        """Test getting a preference."""
        with patch('src.memory.preferences.PreferencesManager') as mock_mgr:
            mock_mgr.get_preference.return_value = "dark"
            
            result = await manage_preferences(
                action="get",
                key="theme",
                user_id=123
            )
            
            assert "theme" in result
            assert "dark" in result
    
    @pytest.mark.asyncio
    async def test_get_preference_not_found(self):
        """Test getting nonexistent preference."""
        with patch('src.memory.preferences.PreferencesManager') as mock_mgr:
            mock_mgr.get_preference.return_value = None
            
            result = await manage_preferences(
                action="get",
                key="nonexistent",
                user_id=123
            )
            
            assert "not found" in result
    
    @pytest.mark.asyncio
    async def test_get_no_key(self):
        """Test get without key."""
        result = await manage_preferences(action="get", user_id=123)
        assert "key" in result.lower() and "required" in result.lower()
    
    @pytest.mark.asyncio
    async def test_list_preferences(self):
        """Test listing preferences."""
        with patch('src.memory.preferences.PreferencesManager') as mock_mgr:
            mock_mgr.list_preferences.return_value = {
                "public": {"theme": "dark"},
                "private": {"api_key": "secret"}
            }
            
            result = await manage_preferences(action="list", user_id=123)
            
            assert "Preferences" in result
            assert "theme" in result
    
    @pytest.mark.asyncio
    async def test_list_preferences_empty(self):
        """Test listing when no preferences."""
        with patch('src.memory.preferences.PreferencesManager') as mock_mgr:
            mock_mgr.list_preferences.return_value = {"public": {}, "private": {}}
            
            result = await manage_preferences(action="list", user_id=123)
            
            assert "No preferences" in result
    
    @pytest.mark.asyncio
    async def test_delete_preference(self):
        """Test deleting a preference."""
        with patch('src.memory.preferences.PreferencesManager') as mock_mgr:
            mock_mgr.delete_preference.return_value = "✅ Deleted"
            
            result = await manage_preferences(
                action="delete",
                key="theme",
                user_id=123
            )
            
            assert "Deleted" in result or "✅" in result
    
    @pytest.mark.asyncio
    async def test_delete_no_key(self):
        """Test delete without key."""
        result = await manage_preferences(action="delete", user_id=123)
        assert "key" in result.lower() and "required" in result.lower()
    
    @pytest.mark.asyncio
    async def test_unknown_action(self):
        """Test unknown action."""
        result = await manage_preferences(action="invalid", user_id=123)
        assert "Unknown action" in result
    
    @pytest.mark.asyncio
    async def test_exception_handling(self):
        """Test exception handling."""
        with patch('src.memory.preferences.PreferencesManager') as mock_mgr:
            mock_mgr.list_preferences.side_effect = Exception("DB error")
            
            result = await manage_preferences(action="list", user_id=123)
            
            assert "Error" in result


class TestManageCalendar:
    """Tests for manage_calendar tool."""
    
    @pytest.mark.asyncio
    async def test_add_event(self):
        """Test adding an event."""
        with patch('src.memory.calendar.CalendarManager') as mock_mgr:
            mock_mgr.add_event.return_value = "✅ Event added"
            
            result = await manage_calendar(
                action="add",
                title="Meeting",
                start_time="2026-02-07 10:00",
                user_id=123
            )
            
            assert "added" in result.lower() or "✅" in result
    
    @pytest.mark.asyncio
    async def test_add_event_missing_args(self):
        """Test add without required args."""
        result = await manage_calendar(action="add")
        assert "title" in result.lower() or "start_time" in result.lower()
    
    @pytest.mark.asyncio
    async def test_remove_event(self):
        """Test removing an event."""
        with patch('src.memory.calendar.CalendarManager') as mock_mgr:
            mock_mgr.remove_event.return_value = "✅ Event removed"
            
            result = await manage_calendar(
                action="remove",
                event_id="evt_123"
            )
            
            assert "removed" in result.lower() or "✅" in result
    
    @pytest.mark.asyncio
    async def test_remove_no_event_id(self):
        """Test remove without event_id."""
        result = await manage_calendar(action="remove")
        assert "event_id" in result.lower()
    
    @pytest.mark.asyncio
    async def test_list_events(self):
        """Test listing events."""
        with patch('src.memory.calendar.CalendarManager') as mock_mgr:
            mock_mgr.list_events.return_value = "📅 2 upcoming events"
            
            result = await manage_calendar(action="list")
            
            assert "events" in result.lower() or "📅" in result
    
    @pytest.mark.asyncio
    async def test_update_event(self):
        """Test updating an event."""
        with patch('src.memory.calendar.CalendarManager') as mock_mgr:
            mock_mgr.update_event.return_value = "✅ Event updated"
            
            result = await manage_calendar(
                action="update",
                event_id="evt_123",
                title="New Title"
            )
            
            assert "updated" in result.lower() or "✅" in result
    
    @pytest.mark.asyncio
    async def test_update_no_event_id(self):
        """Test update without event_id."""
        result = await manage_calendar(action="update")
        assert "event_id" in result.lower()
    
    @pytest.mark.asyncio
    async def test_unknown_action(self):
        """Test unknown action."""
        result = await manage_calendar(action="invalid")
        assert "Unknown action" in result
    
    @pytest.mark.asyncio
    async def test_exception_handling(self):
        """Test exception handling."""
        with patch('src.memory.calendar.CalendarManager') as mock_mgr:
            mock_mgr.list_events.side_effect = Exception("Calendar error")
            
            result = await manage_calendar(action="list")
            
            assert "Error" in result


class TestManageGoals:
    """Tests for manage_goals tool."""
    
    @pytest.mark.asyncio
    async def test_add_goal(self):
        """Test adding a goal."""
        with patch('src.memory.goals.get_goal_manager') as mock_get:
            mock_gm = MagicMock()
            mock_gm.add_goal.return_value = "✅ Goal added: g_abc"
            mock_get.return_value = mock_gm
            
            result = await manage_goals(
                action="add",
                description="Complete project"
            )
            
            assert "added" in result.lower() or "✅" in result
    
    @pytest.mark.asyncio
    async def test_add_goal_no_description(self):
        """Test add without description."""
        with patch('src.memory.goals.get_goal_manager'):
            result = await manage_goals(action="add")
            assert "description" in result.lower()
    
    @pytest.mark.asyncio
    async def test_complete_goal(self):
        """Test completing a goal."""
        with patch('src.memory.goals.get_goal_manager') as mock_get:
            mock_gm = MagicMock()
            mock_gm.complete_goal.return_value = "✅ Goal completed"
            mock_get.return_value = mock_gm
            
            result = await manage_goals(action="complete", goal_id="g_123")
            
            assert "completed" in result.lower() or "✅" in result
    
    @pytest.mark.asyncio
    async def test_complete_no_goal_id(self):
        """Test complete without goal_id."""
        with patch('src.memory.goals.get_goal_manager'):
            result = await manage_goals(action="complete")
            assert "goal_id" in result.lower()
    
    @pytest.mark.asyncio
    async def test_abandon_goal(self):
        """Test abandoning a goal."""
        with patch('src.memory.goals.get_goal_manager') as mock_get:
            mock_gm = MagicMock()
            mock_gm.abandon_goal.return_value = "⚠️ Goal abandoned"
            mock_get.return_value = mock_gm
            
            result = await manage_goals(
                action="abandon",
                goal_id="g_123",
                reason="Changed priorities"
            )
            
            assert "abandoned" in result.lower() or "⚠️" in result
    
    @pytest.mark.asyncio
    async def test_abandon_no_goal_id(self):
        """Test abandon without goal_id."""
        with patch('src.memory.goals.get_goal_manager'):
            result = await manage_goals(action="abandon")
            assert "goal_id" in result.lower()
    
    @pytest.mark.asyncio
    async def test_list_goals(self):
        """Test listing goals."""
        with patch('src.memory.goals.get_goal_manager') as mock_get:
            mock_gm = MagicMock()
            mock_gm.list_goals.return_value = "🎯 3 active goals"
            mock_get.return_value = mock_gm
            
            result = await manage_goals(action="list")
            
            assert "goals" in result.lower() or "🎯" in result
    
    @pytest.mark.asyncio
    async def test_progress_update(self):
        """Test updating goal progress."""
        with patch('src.memory.goals.get_goal_manager') as mock_get:
            mock_gm = MagicMock()
            mock_gm.update_progress.return_value = "📊 Progress: 50%"
            mock_get.return_value = mock_gm
            
            result = await manage_goals(
                action="progress",
                goal_id="g_123",
                progress=50
            )
            
            assert "50" in result or "Progress" in result
    
    @pytest.mark.asyncio
    async def test_progress_missing_args(self):
        """Test progress without required args."""
        with patch('src.memory.goals.get_goal_manager'):
            result = await manage_goals(action="progress", goal_id="g_123")
            assert "progress" in result.lower() and "required" in result.lower()
    
    @pytest.mark.asyncio
    async def test_unknown_action(self):
        """Test unknown action."""
        with patch('src.memory.goals.get_goal_manager'):
            result = await manage_goals(action="invalid")
            assert "Unknown action" in result
    
    @pytest.mark.asyncio
    async def test_exception_handling(self):
        """Test exception handling."""
        with patch('src.memory.goals.get_goal_manager') as mock_get:
            mock_get.side_effect = Exception("Goal error")
            
            result = await manage_goals(action="list")
            
            assert "Error" in result
