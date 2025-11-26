from typing import Any

from pydantic import BaseModel, Field


class Message(BaseModel):
  """Generic message response."""

  message: str


class ErrorResponse(BaseModel):
  """Error response schema."""

  error: str = Field(..., description="Error message")
  detail: str | None = Field(default=None, description="Detailed error information")
  error_code: str | None = Field(default=None, description="Application-specific error code")


class SuccessResponse(BaseModel):
  """Success response schema."""

  success: bool = True
  message: str
  data: Any | None = None


class PaginationParams(BaseModel):
  """Common pagination parameters."""

  page: int = Field(default=1, ge=1, description="Page number")
  page_size: int = Field(default=50, ge=1, le=1000, description="Items per page")


class PaginatedResponse(BaseModel):
  """Generic paginated response."""

  total: int = Field(..., description="Total number of items")
  page: int = Field(..., description="Current page number")
  page_size: int = Field(..., description="Number of items per page")
  total_pages: int = Field(..., description="Total number of pages")

  @classmethod
  def from_items(cls, items: list, total: int, page: int, page_size: int) -> "PaginatedResponse":
    """Create paginated response from items."""
    total_pages = (total + page_size - 1) // page_size
    return cls(total=total, page=page, page_size=page_size, total_pages=total_pages)
