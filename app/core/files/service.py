class FileService:
  async def save(self, filename: str, data: bytes) -> str:
    return filename


file_service = FileService()
