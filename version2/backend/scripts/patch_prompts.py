"""
Patch copilot_mode_router.py with _BASE_RULES insertion.
Run from project root: python3 version2/backend/scripts/patch_prompts.py
"""

FILE = "version2/backend/services/copilot/copilot_mode_router.py"

with open(FILE) as f:
    content = f.read()

# The pattern in the file is:
#             "</mode_persona>\n"
#             "\n"
#             "<mode_rules>\n"
#
# In the file, \n is the two-character escape sequence (backslash + n).
# We need to insert + _BASE_RULES + between the middle "\n" and "<mode_rules>\n"

# The exact string to find (as it appears in the file):
#             "</mode_persona>\n"
#             "\n"
#             "<mode_rules>\n"

old = '            "</mode_persona>\\n"\n            "\\n"\n            "<mode_rules>\\n"'
new = '            "</mode_persona>\\n"\n            "\\n"\n            + _BASE_RULES + "\\n"\n            "\\n"\n            "<mode_rules>\\n"'

count = content.count(old)
if count == 0:
    print("ERROR: Pattern not found! Checking file...")
    # Debug: show the actual bytes around </mode_persona>
    import re
    matches = list(re.finditer(r'</mode_persona>', content))
    print(f"Found {len(matches)} occurrences of </mode_persona> in file")
    for m in matches[:2]:
        start = max(0, m.start() - 20)
        end = min(len(content), m.end() + 50)
        snippet = content[start:end]
        print(f"  Context: {repr(snippet)}")
else:
    content = content.replace(old, new)
    print(f"Inserted _BASE_RULES into {count} mode(s)")

# Replace £ with $ in prompt text
e_count = content.count('\u00a3')  # £ character
if e_count > 0:
    content = content.replace('\u00a3', '$')
    print(f"Replaced {e_count} £ symbols with $")

with open(FILE, 'w') as f:
    f.write(content)

print("Done!")
