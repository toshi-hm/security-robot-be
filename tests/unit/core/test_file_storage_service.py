"""Tests for FileStorageService in app.core.files.service."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest

from app.core.files import storage as storage_module
from app.core.files.service import FileStorageService
from starlette.datastructures import Headers, UploadFile


def _upload_file(*, name: str, data: bytes, content_type: str = "application/octet-stream") -> UploadFile:
    buffer = BytesIO()
    buffer.write(data)
    buffer.seek(0)
    headers = Headers({"content-type": content_type})
    return UploadFile(filename=name, file=buffer, headers=headers)


@pytest.mark.asyncio
async def test_save_upload_prevents_path_traversal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(storage_module, "STORAGE_ROOT", tmp_path / "storage-root")
    service = FileStorageService()

    payload = b"model-binary"
    upload = _upload_file(name="checkpoint.bin", data=payload)

    stored_name, relative_path, size, media_type = await service.save_upload(upload, file_type="..")

    assert stored_name
    assert ".." not in Path(relative_path).parts
    storage_root = (tmp_path / "storage-root").resolve()
    absolute_path = (storage_root / Path(relative_path)).resolve()

    assert absolute_path.exists()
    assert absolute_path.read_bytes() == payload
    assert size == len(payload)
    assert media_type == "application/octet-stream"
    assert absolute_path.is_file()
    assert str(absolute_path).startswith(str(storage_root))


def test_delete_ignores_paths_outside_storage_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(storage_module, "STORAGE_ROOT", tmp_path / "storage")
    service = FileStorageService()

    outside = tmp_path / "outside.txt"
    outside.write_text("keep")

    service.delete("../outside.txt")

    assert outside.exists()


def test_resolve_rejects_paths_that_only_share_prefix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(storage_module, "STORAGE_ROOT", tmp_path / "storage")
    service = FileStorageService()

    sneaky = Path("uploads/../../storage_evil/escape.txt")

    with pytest.raises(ValueError):
        service.resolve(sneaky.as_posix())


def test_delete_does_not_follow_prefix_only_escape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(storage_module, "STORAGE_ROOT", tmp_path / "storage")
    service = FileStorageService()

    escape_root = tmp_path / "storage_evil"
    escape_root.mkdir()
    escape_target = escape_root / "escape.txt"
    escape_target.write_text("keep")

    service.delete("uploads/../../storage_evil/escape.txt")

    assert escape_target.exists()
