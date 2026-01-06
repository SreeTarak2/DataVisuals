"""
Prompt Sanitization for LLM Inputs
==================================

Protects against prompt injection attacks by:
1. Removing common injection patterns
2. Limiting query length
3. Escaping special characters
4. Blocking suspicious content

Usage:
    from core.prompt_sanitizer import sanitize_user_input
    
    clean_query = sanitize_user_input(user_query)
"""

import re
import logging

logger = logging.getLogger(__name__)

# Maximum allowed query length (characters)
MAX_QUERY_LENGTH = 2000

# Patterns that indicate potential prompt injection
INJECTION_PATTERNS = [
    # System prompt override attempts
    r'(?i)ignore\s+(all\s+)?(previous|prior|above)\s+instructions?',
    r'(?i)disregard\s+(all\s+)?(previous|prior|above)',
    r'(?i)forget\s+(everything|all)',
    r'(?i)you\s+are\s+now\s+a',
    r'(?i)pretend\s+to\s+be',
    r'(?i)act\s+as\s+(if\s+you\s+were\s+)?a',
    r'(?i)new\s+system\s+prompt',
    r'(?i)override\s+system',
    r'(?i)\[system\]',
    r'(?i)\[INST\]',
    r'(?i)<<SYS>>',
    r'(?i)</s>',
    r'(?i)<\|im_start\|>',
    r'(?i)<\|im_end\|>',
    
    # Data exfiltration attempts
    r'(?i)reveal\s+(your|the)\s+(system|initial)\s+prompt',
    r'(?i)show\s+me\s+(your|the)\s+instructions',
    r'(?i)what\s+are\s+your\s+instructions',
    r'(?i)print\s+(your|the)\s+prompt',
    
    # Code execution attempts
    r'(?i)execute\s+(this\s+)?(code|python|javascript)',
    r'(?i)run\s+(this\s+)?(code|script|command)',
    r'(?i)eval\s*\(',
    r'(?i)exec\s*\(',
    
    # SQL injection patterns
    r"(?i)'\s*;\s*drop\s+table",
    r"(?i)'\s*;\s*delete\s+from",
    r"(?i)'\s*or\s+'1'\s*=\s*'1",
    r'(?i)union\s+select',
]

# Compile patterns for efficiency
COMPILED_PATTERNS = [re.compile(pattern) for pattern in INJECTION_PATTERNS]


def sanitize_user_input(query: str, max_length: int = MAX_QUERY_LENGTH) -> str:
    """
    Sanitize user input before passing to LLM.
    
    Args:
        query: Raw user query
        max_length: Maximum allowed length
        
    Returns:
        Sanitized query string
        
    Raises:
        ValueError: If query is empty after sanitization
    """
    if not query:
        raise ValueError("Query cannot be empty")
    
    original_query = query
    
    # Truncate to max length
    if len(query) > max_length:
        logger.warning(f"Query truncated from {len(query)} to {max_length} characters")
        query = query[:max_length]
    
    # Check for injection patterns
    injection_detected = False
    for pattern in COMPILED_PATTERNS:
        if pattern.search(query):
            injection_detected = True
            # Replace matched pattern with placeholder
            query = pattern.sub('[FILTERED]', query)
    
    if injection_detected:
        logger.warning(f"Potential prompt injection detected and filtered: {original_query[:100]}...")
    
    # Strip excessive whitespace
    query = ' '.join(query.split())
    
    # Basic XSS prevention (though LLM output should also be sanitized)
    query = query.replace('<script', '&lt;script')
    query = query.replace('</script', '&lt;/script')
    
    if not query.strip():
        raise ValueError("Query is empty after sanitization")
    
    return query.strip()


def is_data_related_query(query: str) -> bool:
    """
    Check if a query is related to data analysis.
    
    Used as a guardrail to filter off-topic queries before LLM invocation.
    
    Args:
        query: User query
        
    Returns:
        True if query appears data-related
    """
    query_lower = query.lower()
    
    # Data analysis keywords
    data_keywords = [
        'data', 'chart', 'graph', 'plot', 'trend', 'analysis', 'analyze',
        'column', 'row', 'table', 'dataset', 'csv', 'excel', 'value',
        'average', 'mean', 'median', 'sum', 'count', 'total', 'max', 'min',
        'correlation', 'distribution', 'outlier', 'pattern', 'compare',
        'group', 'aggregate', 'filter', 'sort', 'top', 'bottom',
        'percentage', 'ratio', 'growth', 'decline', 'increase', 'decrease',
        'forecast', 'predict', 'insight', 'show', 'display', 'visualize',
        'sales', 'revenue', 'profit', 'cost', 'price', 'quantity',
        'category', 'product', 'customer', 'date', 'time', 'month', 'year',
    ]
    
    return any(keyword in query_lower for keyword in data_keywords)


def escape_for_prompt(text: str) -> str:
    """
    Escape text that will be embedded in LLM prompts.
    
    Args:
        text: Text to escape
        
    Returns:
        Escaped text safe for prompt embedding
    """
    if not text:
        return text
    
    # Escape curly braces (common in prompt templates)
    text = text.replace('{', '{{').replace('}', '}}')
    
    # Escape backticks (markdown code blocks)
    text = text.replace('```', '\\`\\`\\`')
    
    return text
