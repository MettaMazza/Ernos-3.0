import re
import ast

response = '[TOOL: start_work_session()]'
tool_matches = []
for m in re.finditer(r'\[TOOL:\s*(\w+)\(', response):
    tool_name_match = m.group(1)
    start = m.end()
    depth = 1
    i = start
    while i < len(response) and depth > 0:
        if response[i] == '(': depth += 1
        elif response[i] == ')': depth -= 1
        i += 1
    args_str = response[start:i-1]
    print(f"Tool: {tool_name_match}, Args: {repr(args_str)}")
