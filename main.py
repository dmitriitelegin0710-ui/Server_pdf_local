from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from urllib.parse import quote
import boto3
from botocore.exceptions import ClientError
import os
import time

app = FastAPI(title="Документация Smart Lift")

S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY")
S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY")
S3_BUCKET = "liftdocs-files"
S3_ENDPOINT = "https://storage.yandexcloud.net"

s3 = boto3.client(
    "s3",
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY,
    region_name="ru-central1"
)

# Кэш файлов
_cache = {"data": None, "timestamp": 0}
CACHE_TTL = 300  # 5 минут


@app.get("/files")
def list_files():
    global _cache

    # Отдаём кэш если он свежий
    if _cache["data"] is not None and (time.time() - _cache["timestamp"]) < CACHE_TTL:
        return JSONResponse(content=_cache["data"])

    try:
        all_objects = []
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=S3_BUCKET):
            all_objects.extend(page.get("Contents", []))

        categories = {}

        for obj in all_objects:
            key = obj["Key"]

            if key.endswith("/"):
                continue

            if "/" in key:
                parts = key.split("/", 1)
                category = parts[0]
                filename = parts[1]
            else:
                category = "Общее"
                filename = key

            if category not in categories:
                categories[category] = []

            categories[category].append({
                "filename": filename,
                "size": obj["Size"],
                "last_modified": obj["LastModified"].isoformat(),
                "url": f"/files/{quote(category)}/{quote(filename)}"
            })

        result = {"total_files": len(all_objects), "categories": categories}

        # Сохраняем в кэш
        _cache["data"] = result
        _cache["timestamp"] = time.time()

        return JSONResponse(content=result)

    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/files/{category}/{filename}")
def get_file(category: str, filename: str):
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


@app.get("/ping")
def ping():
    return {"status": "alive"}


@app.get("/debug")
def debug():
    try:
        response = s3.list_objects_v2(Bucket=S3_BUCKET)
        raw = response.get("Contents", [])
        return {
            "key_set": S3_ACCESS_KEY is not None,
            "secret_set": S3_SECRET_KEY is not None,
            "raw_count": len(raw),
            "first_keys": [obj["Key"] for obj in raw[:5]]
        }
    except ClientError as e:
        return {"error": str(e)}