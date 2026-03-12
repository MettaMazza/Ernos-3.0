import re

with open("pytest_coverage_report.txt", "r") as f:
    lines = f.readlines()

start_idx = 0
for i, line in enumerate(lines):
    if line.startswith("Name") and "Stmts" in line and "Miss" in line:
        start_idx = i + 2
        break

data = []
for line in lines[start_idx:]:
    if line.startswith("---") or line.startswith("TOTAL") or not line.strip():
        if line.startswith("TOTAL"): break
        continue
    parts = line.split()
    if len(parts) >= 4:
        name = parts[0]
        stmts = int(parts[1])
        miss = int(parts[2])
        cover_str = parts[3].replace('%', '')
        cover = int(cover_str)
        if cover < 100:
            data.append((cover, miss, stmts, name))

data.sort(key=lambda x: (x[0], x[1]))

print("# Implementation Plan to Reach 100% Coverage\n")
print("## Target Modules (Sorted by Lowest Coverage)\n")
for cover, miss, stmts, name in data:
    print(f"- **`{name}`**: {cover}% ({miss} missed out of {stmts} statements)")

