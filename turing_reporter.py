import os
import glob
import json
import re
from datetime import datetime
from pathlib import Path

def parse_logs(log_dir="logs/", root_dir="."):
    """Parses Ernos's error traces and system logs for chronological cognitive tape behavior."""
    events = []
    
    # 1. Parse JSONL Trace Logs (error_trace.jsonl, etc)
    for jsonl_file in glob.glob(os.path.join(log_dir, "**/*.jsonl"), recursive=True):
        with open(jsonl_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    if data.get("category") == "TOOL" and str(data.get("source", "")).startswith("tape_"):
                        # Extract context args if available
                        context = data.get("context", {})
                        params = context.get("params", {})
                        args = params.get("args", "no-args")
                        
                        events.append({
                            "time": data.get("timestamp"),
                            "type": "TAPE_OPERATION",
                            "tool": data.get("source"),
                            "details": data.get("error_message", "Success"),
                            "args": args
                        })
                except json.JSONDecodeError:
                    pass

    # 2. Parse Primary ernos_bot.log for TapeMachine specific debug/info emits
    log_files = glob.glob(os.path.join(root_dir, "ernos_bot.log*"))
    tape_regex = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})\s+\[(.*?)\]\s+(.*?TapeMachine|.*tape_.*?):\s*(.*)")
    
    for lf in log_files:
        with open(lf, "r", encoding="utf-8") as f:
            for line in f:
                match = tape_regex.search(line)
                if match:
                    t_str, level, component, msg = match.groups()
                    try:
                        dt = datetime.strptime(t_str, "%Y-%m-%d %H:%M:%S,%f")
                        iso_time = dt.isoformat()
                        events.append({
                            "time": iso_time,
                            "type": "TAPE_INTERNAL",
                            "tool": component.strip(),
                            "details": msg.strip(),
                            "args": ""
                        })
                    except ValueError:
                        pass
                        
    # Sort chronologically
    events.sort(key=lambda x: x["time"] if x["time"] else "")
    
    return events

def generate_report(events, output_file="turing_transparency_report.md"):
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("# Ernos Turing Machine - Chronological Transparency Audit\n")
        f.write("Generated on: " + datetime.now().isoformat() + "\n\n")
        f.write("This document provides a full chronological printout of Ernos's 3D Spatial Memory Tape operations.\n\n")
        
        if not events:
            f.write("*No tape operations found in local logs.*\n")
            return
            
        f.write("| Timestamp | Event Type | Operation / Component | Details | Arguments |\n")
        f.write("|---|---|---|---|---|\n")
        
        for e in events:
            t = e["time"]
            # Limit args length for readability
            args = str(e["args"])[:150] + "..." if len(str(e["args"])) > 150 else str(e["args"])
            # Format row
            row = f"| {t} | {e['type']} | `{e['tool']}` | {e['details']} | `{args}` |\n"
            f.write(row)
            
    print(f"Report generated successfully: {output_file}")

if __name__ == "__main__":
    print("Gathering Ernos Turing Tape events...")
    events = parse_logs(log_dir="logs/", root_dir=".")
    generate_report(events)
