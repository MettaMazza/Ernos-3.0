import re
import os
from datetime import datetime

START_TIME = datetime.strptime("2026-02-23 17:59:00", "%Y-%m-%d %H:%M:%S")
END_TIME = datetime.strptime("2026-02-23 20:57:59", "%Y-%m-%d %H:%M:%S")

def extract_logs(filename, out_filename):
    print(f"Parsing {filename}...")
    log_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")
    
    warnings_errors = []
    current_issue_block = []
    in_target_time = False
    capturing_block = False
    
    if not os.path.exists(filename):
        print(f"File not found: {filename}")
        return

    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            match = log_pattern.match(line)
            if match:
                dt_str = match.group(1)
                try:
                    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                    if START_TIME <= dt <= END_TIME:
                        in_target_time = True
                        if "[WARNING]" in line or "[ERROR]" in line or "WARNING" in line or "ERROR" in line or "Exception" in line or "Traceback" in line:
                            capturing_block = True
                            if current_issue_block:
                                warnings_errors.append("".join(current_issue_block))
                            current_issue_block = [line]
                        else:
                            capturing_block = False
                    else:
                        in_target_time = False
                        capturing_block = False
                except ValueError:
                    if capturing_block:
                        current_issue_block.append(line)
            elif capturing_block:
                current_issue_block.append(line)
                
    if current_issue_block:
        warnings_errors.append("".join(current_issue_block))

    print(f"Found {len(warnings_errors)} issues in {filename}.")
    if warnings_errors:
        with open(out_filename, 'w', encoding='utf-8') as out_f:
            out_f.write("\n==========================================\n".join(warnings_errors))

extract_logs("ernos_bot.log", "extracted_ernos_errors.log")
extract_logs("minecraft.log", "extracted_mc_errors.log")

# Check Turing Report
turing_events = 0
if os.path.exists("turing_transparency_report.md"):
    with open("turing_transparency_report.md", "r") as f:
        for line in f:
            if "|" in line and "TAPE" in line and "2026-02-23T" in line:
                t_str = line.split("|")[1].strip()
                try:
                    # e.g., 2026-02-23T17:38:36.460452
                    dt = datetime.strptime(t_str.split(".")[0], "%Y-%m-%dT%H:%M:%S")
                    if START_TIME <= dt <= END_TIME:
                        turing_events += 1
                except:
                    pass
print(f"Turing Tape events found in range: {turing_events}")
