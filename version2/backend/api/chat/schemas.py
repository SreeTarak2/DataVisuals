from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any


class _Config:
    orm_mode = True
    extra = "forbid"
    use_enum_values = True


class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="User query (max 10,000 characters)",
    )
    context: Optional[Dict[str, Any]] = Field(
        None,
        max_length=5000,
    )
    conversation_id: Optional[str] = None

    @field_validator("message")
    @classmethod
    def validate_message_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Message cannot be empty or whitespace")
        return v.strip()

    class Config(_Config):
        pass


class ChatResponse(BaseModel):
    response: str
    chart: Optional[Dict[str, Any]] = None
    metadata_used: bool = False
    rag_used: bool = False

    class Config(_Config):
        pass


__all__ = ["ChatRequest", "ChatResponse"]
