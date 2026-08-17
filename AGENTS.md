# Agent Instructions (DataSage)

## Non-Negotiable Rules

1. **Never run build commands without explicit user permission.**
   This is a strict, permanent rule. Build commands include (but are not limited to):
   `npm run build`, `npm install`, `pip install`, `make`, `tsc`, bundlers, Docker builds,
   and any command that compiles, installs dependencies, or otherwise produces build artifacts.

   Before running any such command, stop and ask the user for permission first.

2. Prefer editing existing files over creating new ones, and make the fewest changes
   that address the request.
