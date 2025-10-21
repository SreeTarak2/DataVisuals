# tests/test_prompts.py
import pytest
import json
from unittest.mock import MagicMock, patch
from core.prompts import PromptFactory, PromptType, ConversationalResponse


@pytest.fixture
def mock_rag_service():
    """Mock RAG service for testing."""
    service = MagicMock()
    service.search_similar_queries.return_value = [
        {
            "query": "What are the trends in sales data?", 
            "response": "Sales show an upward trend with seasonal patterns",
            "type": "analytical"
        }
    ]
    return service


@pytest.fixture
def sample_schema():
    """Sample schema for testing."""
    return {
        "columns": {
            "Total Sales": "float",
            "Region": "str",
            "Date": "datetime"
        },
        "key_metrics": ["sum(Total Sales)", "mean(Total Sales)"],
        "data_types": {"float": 1, "str": 1, "datetime": 1}
    }


@pytest.fixture
def sample_history():
    """Sample conversation history for testing."""
    return [
        {"role": "user", "content": "Show me sales trends"},
        {"role": "assistant", "content": "I'll create a line chart showing sales over time"}
    ]


class TestPromptFactory:
    """Test cases for the enhanced PromptFactory."""
    
    def test_factory_initialization(self, sample_schema, mock_rag_service):
        """Test factory initialization with all parameters."""
        factory = PromptFactory(
            dataset_context="Sales data for Q1 2024",
            user_preferences={"mode": "learning"},
            schema=sample_schema,
            rag_service=mock_rag_service
        )
        
        assert factory.dataset_context == "Sales data for Q1 2024"
        assert factory.user_prefs["mode"] == "learning"
        assert factory.schema == sample_schema
        assert factory.rag_service == mock_rag_service
    
    def test_conversational_prompt_generation(self, sample_schema, sample_history, mock_rag_service):
        """Test enhanced conversational prompt generation."""
        factory = PromptFactory(
            dataset_context="Sales data",
            schema=sample_schema,
            rag_service=mock_rag_service,
            user_preferences={"mode": "learning"}
        )
        
        prompt = factory.get_prompt(
            PromptType.CONVERSATIONAL,
            history=sample_history,
            chart_options=["bar", "line", "pie"],
            query_type_hints=[],
            mode="learning",
            query="What are the sales trends?"
        )
        
        # Assert prompt contains pedagogical elements
        assert "EXPERT TEACHER DIRECTIVES" in prompt
        assert "Engage Joyfully" in prompt
        assert "Simplify Deeply" in prompt
        assert "Build Learning" in prompt
        assert "learning_arc" in prompt
        assert "confidence" in prompt
        
        # Assert schema is included
        assert "Total Sales" in prompt
        assert "Region" in prompt
        
        # Assert RAG few-shots are included
        assert "RAG FEW-SHOTS" in prompt
    
    def test_rag_few_shots_loading(self, mock_rag_service):
        """Test RAG few-shots loading functionality."""
        factory = PromptFactory(rag_service=mock_rag_service)
        
        few_shots = factory.load_rag_few_shots("sales trends", "dataset_123", limit=2)
        
        assert len(few_shots) == 1
        assert few_shots[0]["query"] == "What are the trends in sales data?"
        assert few_shots[0]["response"] == "Sales show an upward trend with seasonal patterns"
        mock_rag_service.search_similar_queries.assert_called_once_with("sales trends", "dataset_123", 2)
    
    def test_rag_service_unavailable(self):
        """Test behavior when RAG service is unavailable."""
        factory = PromptFactory(rag_service=None)
        
        few_shots = factory.load_rag_few_shots("sales trends", "dataset_123", limit=2)
        
        assert few_shots == []
    
    def test_history_compression(self, sample_history):
        """Test history compression for token efficiency."""
        factory = PromptFactory()
        
        # Test with short history
        short_history = [{"role": "user", "content": "Hello"}]
        summary = factory._summarize_history(short_history)
        assert "User: Hello" in summary
        
        # Test with long history
        long_history = [
            {"role": "user", "content": "What are sales trends?"},
            {"role": "assistant", "content": "I'll show you the sales trends with a line chart"},
            {"role": "user", "content": "Can you make it a bar chart instead?"},
            {"role": "assistant", "content": "Sure, here's a bar chart showing sales by region"},
            {"role": "user", "content": "What about pie chart for product categories?"}
        ]
        
        summary = factory._summarize_history(long_history)
        assert len(summary) < 500  # Should be compressed
        assert "User:" in summary
        assert "Assistant:" in summary
    
    def test_context_compression(self):
        """Test context compression functionality."""
        factory = PromptFactory()
        
        long_context = "A" * 2000  # 2000 character context
        compressed = factory._compress_context(long_context, max_length=1000)
        
        assert len(compressed) <= 1000 + 50  # Allow some buffer for compression markers
        assert "[compressed]" in compressed
        
        # Test with short context
        short_context = "Short context"
        compressed = factory._compress_context(short_context, max_length=1000)
        assert compressed == short_context


class TestValidation:
    """Test cases for output validation."""
    
    def test_valid_conversational_response(self):
        """Test validation of valid conversational response."""
        factory = PromptFactory()
        
        valid_response = {
            "response_text": "Great question! Let's explore your sales data together.",
            "chart_config": None,
            "story_elements": {
                "hook": "Sales show interesting patterns",
                "key_findings": ["Trend 1", "Trend 2"],
                "business_impact": "This affects profitability",
                "next_questions": ["What drives this?", "How can we improve?"]
            },
            "confidence": "High",
            "learning_arc": {
                "hook": "Fascinating insight!",
                "analogy": "Think of sales like a heartbeat",
                "explanation": "The data shows clear patterns",
                "reflection": "What surprises you most?"
            }
        }
        
        validation = factory.render_and_validate(
            PromptType.CONVERSATIONAL, 
            json.dumps(valid_response)
        )
        
        assert validation["validation"]["valid"] is True
        assert validation["validation"]["parsed"]["response_text"] == valid_response["response_text"]
        assert validation["validation"]["parsed"]["confidence"] == "High"
    
    def test_invalid_json_response(self):
        """Test validation of invalid JSON response."""
        factory = PromptFactory()
        
        invalid_response = "This is not valid JSON"
        
        validation = factory.render_and_validate(
            PromptType.CONVERSATIONAL,
            invalid_response
        )
        
        assert validation["validation"]["valid"] is False
        assert validation["validation"]["parsed"] is None
        assert "error" in validation["validation"]
    
    def test_missing_required_fields(self):
        """Test validation of response missing required fields."""
        factory = PromptFactory()
        
        incomplete_response = {
            "response_text": "Some response",
            # Missing confidence and learning_arc
        }
        
        validation = factory.render_and_validate(
            PromptType.CONVERSATIONAL,
            json.dumps(incomplete_response)
        )
        
        assert validation["validation"]["valid"] is False
        assert "error" in validation["validation"]
    
    def test_json_extraction_from_text(self):
        """Test JSON extraction from text containing other content."""
        factory = PromptFactory()
        
        response_with_text = """
        Here's my analysis:
        {
            "response_text": "The sales data shows clear trends",
            "chart_config": null,
            "story_elements": {},
            "confidence": "High",
            "learning_arc": {
                "hook": "Interesting!",
                "analogy": "Like a roller coaster",
                "explanation": "Clear patterns emerge",
                "reflection": "What do you think?"
            }
        }
        This concludes my analysis.
        """
        
        validation = factory.render_and_validate(
            PromptType.CONVERSATIONAL,
            response_with_text
        )
        
        assert validation["validation"]["valid"] is True
        assert validation["validation"]["parsed"]["response_text"] == "The sales data shows clear trends"


class TestPromptModes:
    """Test different prompt modes."""
    
    def test_learning_mode(self, sample_schema, sample_history):
        """Test learning mode prompt generation."""
        factory = PromptFactory(
            schema=sample_schema,
            user_preferences={"mode": "learning"}
        )
        
        prompt = factory.get_prompt(
            PromptType.CONVERSATIONAL,
            history=sample_history,
            chart_options=["bar", "line"],
            mode="learning",
            query="What are the trends?"
        )
        
        assert "learning" in prompt.lower()
        assert "analogy" in prompt.lower()
        assert "explanation" in prompt.lower()
    
    def test_forecasting_prompt(self):
        """Test forecasting prompt generation."""
        factory = PromptFactory()
        
        historical_data = {
            "sales": [100, 120, 110, 130, 140],
            "dates": ["2024-01", "2024-02", "2024-03", "2024-04", "2024-05"]
        }
        
        prompt = factory.get_prompt(
            PromptType.FORECASTING,
            historical_data=historical_data,
            forecast_horizon="30 days"
        )
        
        assert "FORECASTING" in prompt
        assert "predict" in prompt.lower()
        assert "confidence intervals" in prompt.lower()
        assert "30 days" in prompt


class TestErrorRecovery:
    """Test error recovery functionality."""
    
    def test_error_recovery_prompt(self):
        """Test error recovery prompt generation."""
        factory = PromptFactory()
        
        error_context = "JSON parsing failed"
        user_query = "Show me sales trends"
        
        prompt = factory.get_prompt(
            PromptType.ERROR_RECOVERY,
            error_context=error_context,
            user_query=user_query
        )
        
        assert "ERROR CONTEXT" in prompt
        assert error_context in prompt
        assert user_query in prompt
        assert "RECOVERY STRATEGY" in prompt


class TestPerformanceOptimization:
    """Test performance optimization features."""
    
    def test_token_efficiency(self, sample_history):
        """Test that prompts are optimized for token usage."""
        factory = PromptFactory(
            dataset_context="Sales data with many columns and detailed information " * 100
        )
        
        prompt = factory.get_prompt(
            PromptType.CONVERSATIONAL,
            history=sample_history,
            chart_options=["bar", "line", "pie"],
            mode="learning",
            query="What are the trends?"
        )
        
        # Prompt should be reasonable length (under 2000 tokens ≈ 8000 characters)
        assert len(prompt) < 8000
    
    def test_history_compression_performance(self):
        """Test history compression performance."""
        factory = PromptFactory()
        
        # Create long history
        long_history = []
        for i in range(20):
            long_history.append({
                "role": "user",
                "content": f"This is a very long message number {i} with lots of details and information that should be compressed for token efficiency"
            })
            long_history.append({
                "role": "assistant", 
                "content": f"This is a very long response number {i} with lots of details and information that should be compressed for token efficiency"
            })
        
        summary = factory._summarize_history(long_history)
        
        # Should be significantly compressed
        original_length = sum(len(msg["content"]) for msg in long_history)
        assert len(summary) < original_length / 4  # At least 75% compression


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
