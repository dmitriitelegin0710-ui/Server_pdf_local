from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from urllib.parse import quote
import os

app = FastAPI(title="Документация Smart Lift")

DOCS_PATH = "./docs"  # Папка с PDF файлами


def iter_file(path: str, chunk_size: int = 1024 * 64):
    """Генератор для стриминга файла по частям"""
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            yield chunk


@app.get("/files")
def list_files():
    """Получить список всех PDF файлов с категориями (подпапками)"""
    result = {}

    if not os.path.exists(DOCS_PATH):
        return JSONResponse(content={"categories": {}})

    for root, dirs, files in os.walk(DOCS_PATH):
        pdfs = [f for f in files if f.lower().endswith(".pdf")]
        if pdfs:
            # Категория = имя подпапки относительно DOCS_PATH
            category = os.path.relpath(root, DOCS_PATH)
            if category == ".":
                category = "Общее"
            result[category] = pdfs

    return JSONResponse(content={"categories": result})


@app.get("/files/{category}/{filename}")
def get_file(category: str, filename: str):
    """Стриминг PDF файла по категории и имени"""

    # Защита от path traversal атак
    if ".." in category or ".." in filename:
        raise HTTPException(status_code=400, detail="Недопустимый путь")

    if category == "Общее":
        file_path = os.path.join(DOCS_PATH, filename)
    else:
        file_path = os.path.join(DOCS_PATH, category, filename)

    # Проверяем что файл реально внутри DOCS_PATH
    abs_docs = os.path.realpath(DOCS_PATH)
    abs_file = os.path.realpath(file_path)
    if not abs_file.startswith(abs_docs):
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Файл не найден")

    # Кириллика в заголовках через RFC 5987
    encoded_filename = quote(filename)

    return StreamingResponse(
        iter_file(file_path),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{encoded_filename}",
            "Content-Length": str(os.path.getsize(file_path)),
        }
    )


@app.get("/health")
def health():
    return {"status": "ok"}