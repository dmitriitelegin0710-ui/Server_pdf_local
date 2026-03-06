from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from urllib.parse import quote
import boto3
from botocore.exceptions import ClientError
import os

app = FastAPI(title="Документация Smart Lift")

# Яндекс Object Storage настройки
S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY")      # Идентификатор ключа
S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY")      # Секретный ключ
S3_BUCKET = "liftdocs-files"
S3_ENDPOINT = "https://storage.yandexcloud.net"

s3 = boto3.client(
    "s3",
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY,
    region_name="ru-central1"
)


@app.get("/files")
def list_files():
    """Получить список всех PDF файлов с категориями (подпапками)"""
    try:
        response = s3.list_objects_v2(Bucket=S3_BUCKET)
        result = {}

        for obj in response.get("Contents", []):
            key = obj["Key"]
            if not key.lower().endswith(".pdf"):
                continue

            parts = key.split("/")
            if len(parts) == 1:
                category = "Общее"
                filename = parts[0]
            else:
                category = parts[0]
                filename = parts[-1]

            if category not in result:
                result[category] = []
            result[category].append(filename)

        return JSONResponse(content={"categories": result})

    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/files/{category}/{filename}")
def get_file(category: str, filename: str):
    """Стриминг PDF файла по категории и имени"""

    if ".." in category or ".." in filename:
        raise HTTPException(status_code=400, detail="Недопустимый путь")

    if category == "Общее":
        key = filename
    else:
        key = f"{category}/{filename}"

    try:
        obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
    except ClientError:
        raise HTTPException(status_code=404, detail="Файл не найден")

    encoded_filename = quote(filename)

    def iter_s3():
        for chunk in obj["Body"].iter_chunks(chunk_size=1024 * 64):
            yield chunk

    return StreamingResponse(
        iter_s3(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{encoded_filename}",
            "Content-Length": str(obj["ContentLength"]),
        }
    )


@app.get("/health")
def health():
    return {"status": "ok"}