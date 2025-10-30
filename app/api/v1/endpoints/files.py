"""API endpoints for managing uploaded files."""

from __future__ import annotations

import json
from typing import Any

from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.files import (
  FileDeleteResponse,
  FileListResponse,
  FileMetadataResponse,
  FileUploadResponse,
)
from app.services import FileService
from fastapi import APIRouter, Depends, Form, HTTPException, Query, UploadFile, status

router = APIRouter()


@router.post('/', response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
  file: UploadFile,
  file_type: str = Form(..., description='Logical type of the file (model, log, config, etc.)'),
  training_job_id: int | None = Form(None, description='Associated training job identifier'),
  description: str | None = Form(None, description='Optional file description'),
  metadata: str | None = Form(None, description='Arbitrary JSON metadata as a string'),
  db: AsyncSession = Depends(get_db),
) -> FileUploadResponse:
  """Persist an uploaded file and return its metadata."""

  metadata_dict: dict[str, Any] | None = None
  if metadata:
    try:
      metadata_dict = json.loads(metadata)
    except json.JSONDecodeError as exc:
      raise HTTPException(status.HTTP_400_BAD_REQUEST, detail='metadata must be valid JSON') from exc

  service = FileService(db)
  record = await service.save_upload(
    upload=file,
    file_type=file_type,
    training_job_id=training_job_id,
    description=description,
    metadata=metadata_dict,
  )
  return FileUploadResponse.model_validate(record, from_attributes=True)


@router.get('/list', response_model=FileListResponse)
async def list_files(
  page: int = Query(1, ge=1, description='Page number (1-indexed)'),
  page_size: int = Query(20, ge=1, le=100, description='Number of items per page'),
  db: AsyncSession = Depends(get_db),
) -> FileListResponse:
  """Return paginated file metadata entries."""

  service = FileService(db)
  records, total = await service.list_files(page, page_size)
  payload = [
    FileMetadataResponse.model_validate(record, from_attributes=True)
    for record in records
  ]
  return FileListResponse(total=total, page=page, page_size=page_size, files=payload)


@router.get('/{file_id}', response_model=FileMetadataResponse)
async def get_file_metadata(
  file_id: int,
  db: AsyncSession = Depends(get_db),
) -> FileMetadataResponse:
  """Retrieve metadata for a single file."""

  service = FileService(db)
  record = await service.get_file(file_id)
  if record is None:
    raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f'File {file_id} not found')
  return FileMetadataResponse.model_validate(record, from_attributes=True)


@router.delete('/{file_id}', response_model=FileDeleteResponse)
async def delete_file(
  file_id: int,
  db: AsyncSession = Depends(get_db),
) -> FileDeleteResponse:
  """Delete a stored file and its metadata."""

  service = FileService(db)
  record = await service.get_file(file_id)
  if record is None:
    raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f'File {file_id} not found')

  await service.delete_file(record)
  return FileDeleteResponse(id=file_id, filename=record.filename, message='File deleted successfully')


@router.get('/{file_id}/download')
async def download_file(
  file_id: int,
  db: AsyncSession = Depends(get_db),
) -> FileResponse:
  """Stream the stored binary file back to the client."""

  service = FileService(db)
  record = await service.get_file(file_id)
  if record is None:
    raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f'File {file_id} not found')

  try:
    path = service.resolve_path(record)
  except (FileNotFoundError, ValueError) as exc:
    raise HTTPException(status.HTTP_404_NOT_FOUND, detail='Stored file is missing') from exc

  return FileResponse(
    path,
    media_type=record.content_type,
    filename=record.original_filename,
  )
