"""
Narrative Services
==================
Services for transforming analytical findings into narrative stories.

Modules:
    - story_weaver: Main engine for weaving findings into stories

Author: DataSage Team
"""

from services.narrative.story_weaver import StoryWeaver, story_weaver

__all__ = ["StoryWeaver", "story_weaver"]
