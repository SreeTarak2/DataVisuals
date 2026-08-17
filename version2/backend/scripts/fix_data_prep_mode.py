"""
Fix the corrupted data_prep mode in copilot_mode_router.py.
The refactoring script left old inline system_instruction content after the compose call.
"""

from pathlib import Path

TARGET = Path(__file__).resolve().parent.parent / "services" / "copilot" / "copilot_mode_router.py"
content = TARGET.read_text()

# Find the corrupted data_prep compose call end
# Pattern: example=_DATA_PREP_EXAMPLE,\n        ),
# Followed by:  Missing values: Which columns...
# We need to REMOVE from " Missing values:" to the end of COPILOT_MODES (before MODE_PHASES)

marker = "example=_DATA_PREP_EXAMPLE,\n        ),"
idx = content.find(marker)
if idx == -1:
    print("ERROR: Could not find marker")
    exit(1)

# After the marker, find " Missing values:" which starts the leftover
leftover_start = content.find(" Missing values:", idx + len(marker))
if leftover_start == -1:
    # Maybe it's on the same line
    leftover_start = content.find(", Missing values:", idx + len(marker))

if leftover_start == -1:
    print("ERROR: Could not find leftover start")
    print(content[idx:idx+500])
    exit(1)

print(f"Found good compose call ending at {idx + len(marker)}")
print(f"Leftover starts at {leftover_start}")

# Find MODE_PHASES starting
modes_start = content.find("\nMODE_PHASES = {")
if modes_start == -1:
    print("ERROR: Could not find MODE_PHASES")
    exit(1)

# We want to keep everything up to the good end of the compose call,
# then add the closing of the data_prep config entry and the COPILOT_MODES dict,
# then MODE_PHASES

# The correct closing sequence for this mode is:
#         example=_DATA_PREP_EXAMPLE,
#         ),
#     ),
# }
# \n\nMODE_PHASES

new_content = (
    content[:idx + len(marker)] +  # Keep up to the compose call closing
    "\n    ),\n}\n\n" +             # Close the mode config and the dict  
    content[modes_start + 1:]       # Continue from MODE_PHASES
)

TARGET.write_text(new_content)
print(f"✅ Fixed! Wrote {TARGET}")
print(f"File is now {len(new_content)} chars")
print(f"Removed {len(content) - len(new_content)} chars of leftover content")
