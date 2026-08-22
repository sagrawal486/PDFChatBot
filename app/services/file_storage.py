from pathlib import Path

from fastapi import UploadFile


UPLOAD_DIR = Path("uploads")

UPLOAD_DIR.mkdir(
    parents=True,
    exist_ok=True
)


async def save_file(file: UploadFile,) -> str:

    file_path = UPLOAD_DIR / file.filename

    with file_path.open("wb") as buffer:

        while chunk := await file.read(1024 * 1024):

            buffer.write(chunk)

    return str(file_path)
