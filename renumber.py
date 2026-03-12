import re
import sys

def renumber_file(filepath):
    with open(filepath, 'r') as f:
        lines = f.readlines()
        
    out_lines = []
    counter = 1
    
    for line in lines:
        # Match lines starting with numbers like "41. something"
        # Only match if it actually looks like a test step (digit followed by dot and space)
        if re.match(r'^\d+\.\s', line):
            # Replace the leading number with the current counter
            line = re.sub(r'^\d+', str(counter), line)
            counter += 1
        out_lines.append(line)
        
    with open(filepath, 'w') as f:
        f.writelines(out_lines)

    print(f"Renumbered up to {counter - 1} items.")

if __name__ == "__main__":
    renumber_file("MASTER_SYSTEM_TEST.md")
