import asyncio
from unittest.mock import AsyncMock, patch
import pytest

# Simple script to run the test manually and print debugging info
def run_test():
    pytest.main(["-s", "-v", "tests/bot/cogs/test_chat_provenance.py"])

if __name__ == "__main__":
    run_test()
