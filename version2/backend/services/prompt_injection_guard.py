"""Prompt injection detection and mitigation.

Detects common injection patterns:
- Prompt override attempts ("ignore previous instructions...")
- Jailbreak patterns ("pretend you are...")
- Encoding tricks (base64, ROT13, etc.)
"""
import re
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

# Patterns that indicate prompt injection attempts
INJECTION_PATTERNS = [
    r"(?i)\b(ignore|disregard|forget)\s+(all\s+)?previous",
    r"(?i)\b(system|system\s+prompt|instructions?):\s*you\s+are",
    r"(?i)\bpretend\s+(you\s+are|to\s+be)",
    r"(?i)\b(act\s+as|role\s+play\s+as)",
    r"(?i)\b(jailbreak|bypass|override)",
    r"(?i)\[system\]|\[admin\]|\[root\]",
    r"(?i)<!--.*?-->|\/\/.*?\/\/",  # HTML/JS comments
    r"(?i)eval\s*\(|exec\s*\(|__import__|subprocess",  # Code execution
]

# Suspicious encoding patterns
ENCODING_PATTERNS = [
    r"base64:|base64\s*decode",
    r"rot13|rot-13|rot_13",
    r"hex\s*|0x[0-9a-f]+",
    r"unicode|&#x?[0-9a-f]+",
]

# Maximum query length to prevent token exhaustion
MAX_QUERY_LENGTH = 5000

# Maximum consecutive special characters (prevents noise)
MAX_CONSECUTIVE_SPECIALS = 10


def detect_injection_attempt(text: str) -> Tuple[bool, str]:
    """Detect if query contains injection patterns. Returns (is_injection, reason)."""
    if not text or len(text) > MAX_QUERY_LENGTH:
        return True, "Query too long or empty"
    
    text_lower = text.lower()
    
    # Check injection patterns
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, text):
            return True, f"Detected injection pattern: {pattern[:50]}"
    
    # Check encoding patterns
    for pattern in ENCODING_PATTERNS:
        if re.search(pattern, text):
            return True, f"Detected suspicious encoding: {pattern[:50]}"
    
    # Check for excessive special characters
    special_char_sequences = re.findall(r"[^a-zA-Z0-9\s.,'\"!?-]{3,}", text)
    if special_char_sequences:
        longest = max(special_char_sequences, key=len)
        if len(longest) > MAX_CONSECUTIVE_SPECIALS:
            return True, f"Too many consecutive special characters: {longest[:30]}"
    
    return False, ""


def sanitize_and_validate(text: str) -> Tuple[bool, str, str]:
    """Sanitize user query. Returns (is_valid, reason, sanitized_text)."""
    if not text:
        return False, "Empty query", ""
    
    # Trim whitespace
    text = text.strip()
    
    # Check for injection
    is_injection, reason = detect_injection_attempt(text)
    if is_injection:
        logger.warning(f"Query rejected (injection): {reason}")
        return False, f"Query rejected: {reason}", ""
    
    # Basic HTML/XML tag removal
    text = re.sub(r"<[^>]+>", "", text)
    
    # Normalize whitespace  (collapse multiple spaces)
    text = re.sub(r"\s+", " ", text).strip()
    
    if len(text) > MAX_QUERY_LENGTH:
        return False, "Query too long after sanitization", ""
    
    return True, "", text
