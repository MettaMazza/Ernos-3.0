import pytest
import os
import json
from unittest.mock import AsyncMock, patch, MagicMock
from src.core.critical_review import CriticalSelfReview, _parse_judge_output, _log_review

@pytest.fixture
def critic():
    return CriticalSelfReview()

# --- review() tests ---

@pytest.mark.asyncio
async def test_review_no_bot():
    res = await CriticalSelfReview.review("My doc", "Your doc", bot=None)
    assert res["verdict"] == "CLARIFY"
    assert res["confidence"] == 0.0
    assert "No bot instance" in res["reasoning"]

@pytest.mark.asyncio
@patch('src.agents.spawner.AgentSpawner.spawn_many', new_callable=AsyncMock)
@patch('src.agents.spawner.AgentSpawner.spawn', new_callable=AsyncMock)
@patch('src.core.critical_review._log_review')
@patch('src.core.critical_review._parse_judge_output')
async def test_review_success_concede(mock_parse, mock_log, mock_spawn, mock_spawn_many):
    bot_mock = MagicMock()
    
    # Mocking Defender and Challenger
    mock_res_def = MagicMock()
    mock_res_def.status.value = "completed"
    mock_res_def.output = "Defender argument"
    
    mock_res_chal = MagicMock()
    mock_res_chal.status.value = "completed"
    mock_res_chal.output = "Challenger argument"
    
    # The aggregated result obj
    agg_res = MagicMock()
    agg_res.results = [mock_res_def, mock_res_chal]
    mock_spawn_many.return_value = agg_res
    
    # Mocking Judge
    mock_judge = MagicMock()
    mock_judge.status.value = "completed"
    mock_judge.output = "JUDGEMENT"
    mock_spawn.return_value = mock_judge
    
    mock_parse.return_value = {
        "verdict": "CONCEDE",
        "confidence": 0.9,
        "reasoning": "User is right",
        "recommended_response": "I see your point"
    }
    
    with patch('src.core.drives.DriveSystem') as mock_drive_sys:
        mock_drives = MagicMock()
        mock_drive_sys.return_value = mock_drives
        res = await CriticalSelfReview.review("A", "B", bot=bot_mock)
        
        assert res["verdict"] == "CONCEDE"
        mock_drives.modify_drive.assert_called_with("uncertainty", -10.0)

@pytest.mark.asyncio
@patch('src.agents.spawner.AgentSpawner.spawn_many', new_callable=AsyncMock)
@patch('src.agents.spawner.AgentSpawner.spawn', new_callable=AsyncMock)
@patch('src.core.critical_review._log_review')
@patch('src.core.critical_review._parse_judge_output')
async def test_review_success_hold_low_confidence(mock_parse, mock_log, mock_spawn, mock_spawn_many):
    bot_mock = MagicMock()
    
    mock_res_def = MagicMock()
    mock_res_def.status.value = "completed"
    mock_res_def.output = "Defender"
    
    agg_res = MagicMock()
    agg_res.results = [mock_res_def, MagicMock()]
    mock_spawn_many.return_value = agg_res
    
    mock_judge = MagicMock()
    mock_judge.status.value = "completed"
    mock_judge.output = "JUDGEMENT"
    mock_spawn.return_value = mock_judge
    
    mock_parse.return_value = {
        "verdict": "HOLD",
        "confidence": 0.4,
        "reasoning": "Holding ground",
        "recommended_response": "I think I am right"
    }
    
    with patch('src.core.drives.DriveSystem') as mock_drive_sys:
        mock_drives = MagicMock()
        mock_drive_sys.return_value = mock_drives
        res = await CriticalSelfReview.review("A", "B", bot=bot_mock)
        mock_drives.modify_drive.assert_called_with("uncertainty", 5.0)

@pytest.mark.asyncio
@patch('src.agents.spawner.AgentSpawner.spawn_many', new_callable=AsyncMock)
async def test_review_agents_fail(mock_spawn_many):
    bot_mock = MagicMock()
    agg_res = MagicMock()
    # Both fail
    r1 = MagicMock(); r1.status.value = "failed"; r1.output = ""
    r2 = MagicMock(); r2.status.value = "failed"; r2.output = ""
    agg_res.results = [r1, r2]
    mock_spawn_many.return_value = agg_res
    
    res = await CriticalSelfReview.review("A", "B", bot=bot_mock)
    assert res["verdict"] == "CLARIFY"
    assert "failed" in res["reasoning"].lower()

@pytest.mark.asyncio
@patch('src.agents.spawner.AgentSpawner.spawn_many', new_callable=AsyncMock)
@patch('src.agents.spawner.AgentSpawner.spawn', new_callable=AsyncMock)
async def test_review_judge_fails(mock_spawn, mock_spawn_many):
    bot_mock = MagicMock()
    r1 = MagicMock(); r1.status.value = "completed"; r1.output = "Def"
    agg_res = MagicMock(); agg_res.results = [r1, r1]
    mock_spawn_many.return_value = agg_res
    
    # Judge fails
    mock_judge = MagicMock()
    mock_judge.status.value = "failed"
    mock_spawn.return_value = mock_judge
    
    res = await CriticalSelfReview.review("A", "B", bot=bot_mock)
    assert res["verdict"] == "CLARIFY"
    assert "Judge agent failed" in res["reasoning"]

@pytest.mark.asyncio
@patch('src.agents.spawner.AgentSpawner.spawn_many', side_effect=Exception("Total failure"))
async def test_review_exception(mock_spawn_many):
    bot_mock = MagicMock()
    res = await CriticalSelfReview.review("A", "B", bot=bot_mock)
    assert res["verdict"] == "CLARIFY"
    assert "Total failure" in res["reasoning"]

@pytest.mark.asyncio
@patch('src.agents.spawner.AgentSpawner.spawn_many', new_callable=AsyncMock)
@patch('src.agents.spawner.AgentSpawner.spawn', new_callable=AsyncMock)
@patch('src.core.critical_review._log_review')
@patch('src.core.critical_review._parse_judge_output')
async def test_review_drive_exception(mock_parse, mock_log, mock_spawn, mock_spawn_many):
    bot_mock = MagicMock()
    r1 = MagicMock(); r1.status.value = "completed"; r1.output = "Def"
    agg_res = MagicMock(); agg_res.results = [r1, r1]
    mock_spawn_many.return_value = agg_res
    
    mock_judge = MagicMock(); mock_judge.status.value = "completed"; mock_judge.output = "J"
    mock_spawn.return_value = mock_judge
    
    mock_parse.return_value = {"verdict": "CONCEDE", "confidence": 0.9, "reasoning": "", "recommended_response": ""}
    
    with patch('src.core.drives.DriveSystem', side_effect=Exception("Drive system boom")):
        res = await CriticalSelfReview.review("A", "B", bot=bot_mock)
        assert res["verdict"] == "CONCEDE" # Still returns parsed verdict correctly

# --- _parse_judge_output tests ---

def test_parse_judge_output_concede():
    out = "VERDICT: CONCEDE\nCONFIDENCE: 0.8\nREASONING: User is right\nRECOMMENDED_RESPONSE: OK"
    res = _parse_judge_output(out)
    assert res["verdict"] == "CONCEDE"
    assert res["confidence"] == 0.8
    assert res["reasoning"] == "User is right"
    assert res["recommended_response"] == "OK"

def test_parse_judge_output_hold_multiline():
    out = "VERDICT: HOLD THE LINE\nCONFIDENCE: 0.99\nREASONING: Because\nI said so.\nRECOMMENDED_RESPONSE: No way"
    res = _parse_judge_output(out)
    assert res["verdict"] == "HOLD"
    assert res["confidence"] == 0.99
    assert res["reasoning"] == "Because I said so."
    assert res["recommended_response"] == "No way"

def test_parse_judge_output_clarify_and_malformed():
    out = "VERDICT: COMPLETELY WRONG AND NOT ON LIST\nCONFIDENCE: VERY HIGH\nREASONING: Stuff"
    res = _parse_judge_output(out)
    assert res["verdict"] == "CLARIFY"
    assert res["confidence"] == 0.5 # Default fallback logic? Oh it skips ValueError on conversion
    assert res["reasoning"] == "Stuff"

# --- _log_review tests ---

def test_log_review_success(tmp_path, monkeypatch):
    log_file = tmp_path / "self_reviews.jsonl"
    monkeypatch.setattr('src.core.critical_review.REVIEW_LOG_PATH', str(log_file))
    
    _log_review("Mine", "Yours", {"verdict": "CONCEDE", "confidence": 0.8, "reasoning": "Because"}, "U1")
    
    assert log_file.exists()
    content = json.loads(log_file.read_text())
    assert content["my_position"] == "Mine"

def test_log_review_exception(monkeypatch):
    def boom(*args, **kwargs): raise OSError("boom")
    monkeypatch.setattr('os.makedirs', boom)
    # Should safely catch and log exception without raising
    _log_review("Mine", "Yours", {"verdict": "CONCEDE", "confidence": 0.8, "reasoning": "Because"}, "U1")

