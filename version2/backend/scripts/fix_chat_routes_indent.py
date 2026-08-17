"""Fix over-indentation in the inner body of _stream_from_copilot."""
path = "version2/backend/api/chat/routes.py"
with open(path) as f:
    lines = f.readlines()

# The fix: reduce indentation by 8 for lines with 48-56 spaces within the section.
# Lines at 52 -> 44, lines at 56 -> 48, lines at 48 -> 40
# This is the body of `async for chunk in copilot_service.process_streaming(`
# which is at 40 spaces.

def count_leading(s):
    return len(s) - len(s.lstrip())

fix_start = None
fix_end = None

for i, line in enumerate(lines):
    # Find the line with "):" at 40 spaces - this closes the async for call
    stripped = line.strip()
    if stripped == "):" and count_leading(line) == 40 and i > 410 and i < 450:
        fix_start = i + 1  # Body starts after this
        break

if fix_start is None:
    print("ERROR: Could not find end of async for call")
    exit(1)

# Find the line with "except asyncio.CancelledError:" at 36 spaces
for i in range(fix_start, len(lines)):
    stripped = lines[i].strip()
    indent = count_leading(lines[i])
    if indent == 36 and "except " in stripped:
        fix_end = i
        break

if fix_end is None:
    print("ERROR: Could not find except")
    fix_end = fix_start + 30

print(f"Fixing lines {fix_start + 1} to {fix_end}")

for i in range(fix_start, fix_end):
    line = lines[i]
    stripped = line.rstrip()
    if not stripped:
        continue
    indent = count_leading(line)
    
    # Lines at 52, 56, 48 need -8
    if indent in (52, 56, 48):
        new_indent = indent - 8
        lines[i] = " " * new_indent + stripped.lstrip() + "\n"
    # Lines at 40, 44 are correct

with open(path, 'w') as f:
    f.writelines(lines)

print("Done")
