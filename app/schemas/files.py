"""Pydantic schemas for file management endpoints."""

from __future__ import annotations

from datetime import datetime
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.training import TrainingAlgorithm


class FileMetadataResponse(BaseModel):
  """Response schema for file metadata."""

  model_config = ConfigDict(from_attributes=True, populate_by_name=True)

  id: int
  filename: str
  original_filename: str
  file_path: str
  file_size: int
  file_type: str
  content_type: str
  training_job_id: Optional[int]
  description: Optional[str]
  metadata: Optional[dict[str, Any]] = Field(default=None, alias='metadata_', serialization_alias='metadata')
  created_at: datetime
  updated_at: datetime


class FileUploadResponse(FileMetadataResponse):
  """Response schema for file uploads."""

  upload_url: Optional[str] = None


class FileListResponse(BaseModel):
  """Response schema for file list."""

  total: int
  page: int
  page_size: int
  files: list[FileMetadataResponse]


class FileDeleteResponse(BaseModel):
  """Response schema for file deletion."""

  id: int
  filename: str
  message: str


class ModelFileInfo(BaseModel):
  """Information about a saved model file."""

  model_config = ConfigDict(from_attributes=True)

  filename: str
  file_size: int
  algorithm: TrainingAlgorithm
  training_session_id: Optional[int] = None
  created_at: datetime
  metadata: Optional[dict[str, Any]] = None


class ModelListResponse(BaseModel):
  """Response schema for model list."""

  total: int
  models: list[ModelFileInfo]


class ModelDownloadResponse(BaseModel):
  """Response schema for model download."""

  filename: str
  download_url: str
  content_type: str
  file_size: int
