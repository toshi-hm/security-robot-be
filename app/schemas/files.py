from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


# File Upload/Download Schemas

class FileUploadResponse(BaseModel):
  """Response schema for file upload."""
  id: int
  filename: str
  original_filename: str
  file_path: str
  file_size: int
  file_type: str
  content_type: str
  upload_url: Optional[str] = None
  created_at: datetime


class FileMetadataResponse(BaseModel):
  """Response schema for file metadata."""
  model_config = ConfigDict(from_attributes=True)
  
  id: int
  filename: str
  original_filename: str
  file_path: str
  file_size: int
  file_type: str
  content_type: str
  training_job_id: Optional[int]
  description: Optional[str]
  metadata: Optional[dict]
  created_at: datetime
  updated_at: datetime


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


# Model File Schemas

class ModelFileInfo(BaseModel):
  """Information about a saved model file."""
  filename: str
  file_size: int
  algorithm: str
  training_session_id: Optional[int] = None
  created_at: datetime
  metadata: Optional[dict] = None


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
