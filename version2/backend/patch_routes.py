"""
⚠️ patch_routes.py is DEPRECATED — patches are now inlined directly in routes.py.

This file previously applied string-replacement patches to api/chat/routes.py at
runtime. All patches (send_lock, active_tasks, copilot_service integration,
backpressure queue, cancel handling, non-stream wrapper, cleanup) are now
permanently inlined directly in the routes file.

This file exists solely to prevent import errors if anything still references it.
"""

import logging
import warnings

logger = logging.getLogger(__name__)
logger.warning(
    "patch_routes.py is deprecated — all patches are already inlined in routes.py. "
    "This file does nothing."
)
warnings.warn(
    "patch_routes.py is deprecated — remove any references to it.",
    DeprecationWarning,
    stacklevel=2,
)
