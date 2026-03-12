import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from src.lobes.memory.librarian import LibrarianAbility
from pathlib import Path

@pytest.fixture
def librarian_ability():
    return LibrarianAbility(MagicMock())

@pytest.mark.asyncio
async def test_execute_paths_missing(librarian_ability):
    assert "Please provide a valid file path" in await librarian_ability.execute("read")
    assert "File not found" in await librarian_ability.execute("read", path="non_existent.txt")

@pytest.mark.asyncio
async def test_execute_routing(librarian_ability, tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("line1\nline2\nline3")
    p = str(f)

    # Open
    res = await librarian_ability.execute("open book", path=p)
    assert "Opened" in res
    assert "3 lines" in res
    
    # Read (Manual)
    res = await librarian_ability.execute("read page", path=p)
    assert "line1" in res
    
    # Density
    res = await librarian_ability.execute("check density", path=p)
    assert "Density Analysis" in res
    
    # Default (Just path)
    res = await librarian_ability.execute("next", path=p) # "read" not in "next", logic falls to else
    # BUT wait: `elif "read" in instruction.lower():`
    # `elif "density" in instruction.lower():`
    # `else: return self.read_page(...)`
    # So "next" goes to else -> read_page.
    # Cursor should have moved from previous calls?
    # open reset to 0.
    # read page (manual) -> read 50 lines -> cursor at 3.
    # execute("next") -> cursor at 3 -> EOF?
    # Let's verify cursor logic explicitly in separate test.

@pytest.mark.asyncio
async def test_pagination_logic(librarian_ability, tmp_path):
    f = tmp_path / "pager.txt"
    # Create 10 lines
    lines = [f"L{i}" for i in range(10)]
    f.write_text("\n".join(lines))
    p = str(f)
    
    # 1. Open (Reset)
    await librarian_ability.execute("open", path=p)
    
    # 2. Read first 3 lines
    # execute calls `read_page(file_path, lines=50)` default.
    # We can pass lines kwarg if we call execute? NO. execute signature is fixed.
    # But execute signature in code: `async def execute(self, instruction: str, path: str = None, lines: int = 50) -> str:`
    # So we CAN pass lines.
    
    res = await librarian_ability.execute("read", path=p, lines=3)
    assert "L0" in res
    assert "L2" in res
    assert "L3" not in res
    # Cursor should be at 3
    
    # 3. Read next 3 lines (L3, L4, L5)
    res = await librarian_ability.execute("read", path=p, lines=3)
    assert "L3" in res
    assert "L5" in res
    assert "L6" not in res
    
    # 4. Read remaining (L6-L9)
    res = await librarian_ability.execute("read", path=p, lines=10)
    assert "L6" in res
    assert "L9" in res
    
    # 5. EOF
    res = await librarian_ability.execute("read", path=p)
    assert "End of file reached" in res

@pytest.mark.asyncio
async def test_error_handling(librarian_ability, tmp_path):
    f = tmp_path / "bad.txt"
    f.touch()
    
    # Analyze Density Error (Mock read_text failure)
    with patch("pathlib.Path.read_text", side_effect=Exception("Read Err")):
        res = await librarian_ability.execute("density", path=str(f))
        assert "Density Check Error" in res
        
    # Read Page Error (Mock open failure)
    # We need to mock open inside read_page, but `open` is built-in.
    with patch("builtins.open", side_effect=Exception("Access Denied")):
        res = await librarian_ability.execute("read", path=str(f))
        assert "Librarian Read Error" in res
