"""
Output Validation Layer for LLM Responses

Validates LLM outputs against schemas and business rules.
Provides retry logic with progressive refinement prompts.
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when validation fails after all retries"""
    pass


class ChartType(str, Enum):
    """Valid chart types - must match exactly"""
    BAR = "bar"
    LINE = "line"
    PIE = "pie"
    SCATTER = "scatter"
    HISTOGRAM = "histogram"
    HEATMAP = "heatmap"
    BOX = "box"
    VIOLIN = "violin"
    AREA = "area"
    GROUPED_BAR = "grouped_bar"
    TREEMAP = "treemap"


class ConfidenceLevel(str, Enum):
    """Valid confidence levels - must match exactly"""
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class OutputValidator:
    """
    Validates LLM outputs for correctness and completeness.
    """
    
    VALID_CHART_TYPES = {t.value for t in ChartType}
    VALID_CONFIDENCE_LEVELS = {c.value for c in ConfidenceLevel}
    
    def __init__(self, available_columns: Optional[List[str]] = None):
        """
        Initialize validator with dataset context.
        
        Args:
            available_columns: List of actual column names in the dataset
        """
        self.available_columns = available_columns or []
        self.available_columns_lower = {col.lower() for col in self.available_columns}
    
    def validate_conversational_response(
        self, 
        response: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """
        Validate conversational AI response.
        
        Returns:
            (is_valid, list_of_errors)
        """
        errors = []
        
        # Check required fields
        if not response.get("response_text"):
            errors.append("response_text is missing or empty")
        elif not isinstance(response["response_text"], str):
            errors.append("response_text must be a string")
        elif len(response["response_text"]) < 10:
            errors.append(f"response_text too short ({len(response['response_text'])} chars), minimum 10")
        elif len(response["response_text"]) > 5000:
            errors.append(f"response_text too long ({len(response['response_text'])} chars), maximum 5000")
        
        # Check confidence
        confidence = response.get("confidence")
        if not confidence:
            errors.append("confidence is missing")
        elif confidence not in self.VALID_CONFIDENCE_LEVELS:
            errors.append(f"confidence must be one of {self.VALID_CONFIDENCE_LEVELS}, got '{confidence}'")
        
        # Validate chart_config if present
        chart_config = response.get("chart_config")
        if chart_config is not None and chart_config != "null":
            chart_errors = self._validate_chart_config(chart_config)
            errors.extend(chart_errors)
        
        return (len(errors) == 0, errors)
    
    def validate_dashboard_response(
        self,
        response: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """
        Validate dashboard designer response.
        
        Returns:
            (is_valid, list_of_errors)
        """
        errors = []
        
        # Check for dashboard structure
        if "dashboard" not in response:
            errors.append("Missing 'dashboard' key")
            return (False, errors)
        
        dashboard = response["dashboard"]
        
        # Check components
        if "components" not in dashboard:
            errors.append("Missing 'components' in dashboard")
        elif not isinstance(dashboard["components"], list):
            errors.append("components must be an array")
        elif len(dashboard["components"]) == 0:
            errors.append("components array is empty")
        else:
            # Validate each component
            for i, component in enumerate(dashboard["components"]):
                comp_errors = self._validate_component(component, i)
                errors.extend(comp_errors)
        
        return (len(errors) == 0, errors)
    
    def _validate_component(
        self,
        component: Dict[str, Any],
        index: int
    ) -> List[str]:
        """Validate a single dashboard component"""
        errors = []
        prefix = f"Component {index}"
        
        # Check type
        comp_type = component.get("type")
        if not comp_type:
            errors.append(f"{prefix}: missing 'type'")
        elif comp_type not in ["kpi", "chart", "table"]:
            errors.append(f"{prefix}: type must be 'kpi', 'chart', or 'table', got '{comp_type}'")
        
        # Check title
        if not component.get("title"):
            errors.append(f"{prefix}: missing 'title'")
        
        # Check config
        if "config" not in component:
            errors.append(f"{prefix}: missing 'config'")
        elif comp_type == "chart":
            config_errors = self._validate_chart_config(component["config"], prefix)
            errors.extend(config_errors)
        
        return errors
    
    def _validate_chart_config(
        self,
        config: Dict[str, Any],
        prefix: str = "chart_config"
    ) -> List[str]:
        """Validate chart configuration"""
        errors = []
        
        if not isinstance(config, dict):
            errors.append(f"{prefix} must be an object, got {type(config)}")
            return errors
        
        # Check chart type (can be in 'type' or 'chart_type' field)
        chart_type = config.get("type") or config.get("chart_type")
        if not chart_type:
            errors.append(f"{prefix}: missing 'type' or 'chart_type'")
        elif chart_type not in self.VALID_CHART_TYPES:
            errors.append(
                f"{prefix}: invalid chart type '{chart_type}'. "
                f"Must be one of: {', '.join(self.VALID_CHART_TYPES)}"
            )
        
        # Check columns
        columns = config.get("columns", [])
        x_col = config.get("x")
        y_col = config.get("y")
        
        # If x/y provided, use those
        if x_col or y_col:
            columns = [x_col, y_col]
        
        if not columns and chart_type != "histogram":
            errors.append(f"{prefix}: missing 'columns' or 'x'/'y' fields")
        else:
            # Validate column existence
            if self.available_columns:
                for col in columns:
                    if col and col not in self.available_columns:
                        # Try case-insensitive match
                        if col.lower() not in self.available_columns_lower:
                            errors.append(
                                f"{prefix}: column '{col}' not found in dataset. "
                                f"Available: {', '.join(self.available_columns[:10])}"
                            )
        
        return errors
    
    def suggest_fixes(self, errors: List[str]) -> str:
        """
        Generate helpful suggestions based on validation errors.
        
        Args:
            errors: List of validation error messages
            
        Returns:
            Formatted string with fix suggestions
        """
        suggestions = []
        
        for error in errors:
            if "chart type" in error.lower():
                suggestions.append(
                    f"Fix: Use exact chart type values (lowercase): bar, line, pie, scatter, histogram, heatmap"
                )
            elif "column" in error.lower() and "not found" in error.lower():
                suggestions.append(
                    f"Fix: Use ONLY these exact column names: {', '.join(self.available_columns[:10])}"
                )
            elif "response_text" in error.lower() and "empty" in error.lower():
                suggestions.append(
                    f"Fix: Provide a helpful answer in response_text field (minimum 10 characters)"
                )
            elif "confidence" in error.lower():
                suggestions.append(
                    f"Fix: Set confidence to exactly 'High', 'Medium', or 'Low' (case-sensitive)"
                )
        
        return "\n".join(suggestions) if suggestions else "Check the validation errors above."


async def validate_with_retry(
    llm_call_func,
    validator: OutputValidator,
    validation_method: str,
    max_retries: int = 3,
    initial_prompt: str = ""
) -> Dict[str, Any]:
    """
    Call LLM with automatic retry and progressive refinement.
    
    Args:
        llm_call_func: Async function that calls LLM (takes prompt as arg)
        validator: OutputValidator instance
        validation_method: Name of validation method ('validate_conversational_response' or 'validate_dashboard_response')
        max_retries: Maximum number of retry attempts
        initial_prompt: Initial prompt to send to LLM
    
    Returns:
        Validated response dict
        
    Raises:
        ValidationError: If validation fails after all retries
    """
    validate_func = getattr(validator, validation_method)
    
    for attempt in range(max_retries):
        try:
            # Call LLM
            if attempt == 0:
                response = await llm_call_func(initial_prompt)
            else:
                # Progressive refinement: add error details to prompt
                refinement_prompt = f"""{initial_prompt}

PREVIOUS ATTEMPT FAILED VALIDATION:
{chr(10).join(f'- {err}' for err in errors)}

{validator.suggest_fixes(errors)}

Please fix these issues and try again. Return ONLY valid JSON."""
                
                logger.warning(f"Attempt {attempt + 1}/{max_retries} - Retrying with refinement prompt")
                response = await llm_call_func(refinement_prompt)
            
            # Validate response
            is_valid, errors = validate_func(response)
            
            if is_valid:
                logger.info(f"✓ Validation passed on attempt {attempt + 1}/{max_retries}")
                return response
            
            # Log validation errors
            logger.warning(f"✗ Validation failed on attempt {attempt + 1}/{max_retries}:")
            for error in errors:
                logger.warning(f"  - {error}")
            
            # Wait before retry (exponential backoff)
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 1s, 2s, 4s
                logger.info(f"Waiting {wait_time}s before retry...")
                await asyncio.sleep(wait_time)
        
        except Exception as e:
            logger.error(f"Attempt {attempt + 1}/{max_retries} raised exception: {e}")
            if attempt == max_retries - 1:
                raise ValidationError(f"All retries failed. Last error: {e}")
    
    # All retries exhausted
    raise ValidationError(
        f"Validation failed after {max_retries} attempts. "
        f"Final errors: {'; '.join(errors)}"
    )


__all__ = [
    "OutputValidator",
    "ValidationError",
    "ChartType",
    "ConfidenceLevel",
    "validate_with_retry",
]
