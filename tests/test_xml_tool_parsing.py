import pytest
import re
import json
import ast

# Extract the parsing logic from CognitionEngine for isolated testing
# We will UPDATE this function in the test to match what we intend to write in the engine
def parse_xml_tools(response_text):
    xml_tool_pattern = re.compile(r"<tool_call>(.*?)</tool_call>", re.DOTALL)
    xml_matches = xml_tool_pattern.findall(response_text)
    parsed_tools = []
    
    for xml_content in xml_matches:
        try:
            # ROBUST PARSING LOGIC (Mirroring intended fix)
            clean_content = xml_content.strip()
            
            # 1. Remove markdown code blocks if present
            if clean_content.startswith("```json"):
                clean_content = clean_content[7:]
            elif clean_content.startswith("```"):
                clean_content = clean_content[3:]
            if clean_content.endswith("```"):
                clean_content = clean_content[:-3]
            
            clean_content = clean_content.strip()
            
            # 2. Extract JSON object even if surrounded by text
            # Find first { and last }
            start = clean_content.find("{")
            end = clean_content.rfind("}")
            
            if start != -1 and end != -1:
                json_str = clean_content[start:end+1]
                
                tool_data = None
                # Try standard JSON first
                try:
                    tool_data = json.loads(json_str)
                except json.JSONDecodeError:
                    # Try ast.literal_eval for python-like dicts (trailing commas, single quotes)
                    try:
                        tool_data = ast.literal_eval(json_str)
                    except Exception:
                        pass
                
                if isinstance(tool_data, dict) and "name" in tool_data:
                    t_name = tool_data["name"]
                    t_args = tool_data.get("arguments", {})
                    
                    arg_str_parts = []
                    if isinstance(t_args, dict):
                        for k, v in t_args.items():
                            if isinstance(v, str):
                                safe_v = v.replace('"', '\\"')
                                arg_str_parts.append(f'{k}="{safe_v}"')
                            else:
                                arg_str_parts.append(f'{k}={v}')
                    arg_str = ", ".join(arg_str_parts)
                    parsed_tools.append((t_name, arg_str))
        except Exception:
            pass
            
    return parsed_tools

def test_basic_xml_parsing():
    input_text = """
    I will help you.
    <tool_call>
    {"name": "escalate_ticket", "arguments": {"reason": "User request", "priority": "high"}}
    </tool_call>
    """
    tools = parse_xml_tools(input_text)
    assert len(tools) == 1
    name, args = tools[0]
    assert name == "escalate_ticket"
    assert 'reason="User request"' in args
    assert 'priority="high"' in args

def test_markdown_json_parsing():
    input_text = """
    <tool_call>
    ```json
    {"name": "test_tool", "arguments": {"foo": 123}}
    ```
    </tool_call>
    """
    tools = parse_xml_tools(input_text)
    assert len(tools) == 1
    assert tools[0][0] == "test_tool"
    assert 'foo=123' in tools[0][1]

def test_multiline_json_parsing():
    input_text = """
    <tool_call>
    {
      "name": "escalate_ticket",
      "arguments": {
        "reason": "User explicitly requested to talk to a person.",
        "priority": "medium"
      }
    }
    </tool_call>
    """
    tools = parse_xml_tools(input_text)
    assert len(tools) == 1
    name, args = tools[0]
    assert name == "escalate_ticket"
    assert 'priority="medium"' in args

def test_messy_xml_parsing():
    # Case 1: Extra text inside tag
    input_text = """
    <tool_call>
    Here is the json:
    {"name": "test_tool", "arguments": {"x": 1}}
    </tool_call>
    """
    tools = parse_xml_tools(input_text)
    assert len(tools) == 1
    assert tools[0][0] == "test_tool"

def test_trailing_comma_parsing():
    # Case 2: Trailing comma (JSON invalid, but common in LLMs)
    input_text = """
    <tool_call>
    {
      "name": "test_tool",
      "arguments": {
        "x": 1,
      }
    }
    </tool_call>
    """
    tools = parse_xml_tools(input_text)
    assert len(tools) == 1
    assert tools[0][0] == "test_tool"
