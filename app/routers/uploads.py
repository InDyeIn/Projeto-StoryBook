"""Upload e entrega de imagens (avatares, banners, tokens, mapas)."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError

from app.config import settings
from app.deps import CurrentUser, DbDep, verify_csrf
from app.models import Upload

router = APIRouter(tags=["arquivos"])

#: Cada tipo de imagem tem um teto de tamanho — evita guardar um mapa de 8000px
#: como avatar e estourar a banda de quem abre o perfil.
KIND_LIMITS: dict[str, tuple[int, int]] = {
    "avatar": (512, 512),
    "banner": (1600, 500),
    "token": (512, 512),
    "scene": (4000, 4000),
    "attachment": (2000, 2000),
}

ALLOWED_FORMATS = {"PNG": "png", "JPEG": "jpg", "WEBP": "webp", "GIF": "gif"}
SAFE_NAME = re.compile(r"^[a-f0-9]{32}\.(png|jpg|webp|gif)$")


@router.post("/api/upload", dependencies=[Depends(verify_csrf)])
async def upload_image(
    user: CurrentUser,
    db: DbDep,
    file: UploadFile = File(...),
    kind: str = Form("attachment"),
):
    if kind not in KIND_LIMITS:
        raise HTTPException(400, "Tipo de upload desconhecido.")

    raw = await file.read()
    limit = settings.max_upload_mb * 1024 * 1024
    if len(raw) > limit:
        raise HTTPException(413, f"Arquivo maior que {settings.max_upload_mb} MB.")
    if not raw:
        raise HTTPException(400, "Arquivo vazio.")

    # Abrimos com Pillow em vez de confiar no content-type enviado: isso rejeita
    # arquivos que só fingem ser imagem.
    try:
        image = Image.open(__import__("io").BytesIO(raw))
        image.load()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(415, "Não consegui ler essa imagem. Use PNG, JPG, WEBP ou GIF.")

    fmt = (image.format or "").upper()
    if fmt not in ALLOWED_FORMATS:
        raise HTTPException(415, "Formato não suportado. Use PNG, JPG, WEBP ou GIF.")

    extension = ALLOWED_FORMATS[fmt]
    animated = getattr(image, "is_animated", False)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.{extension}"
    destination = settings.upload_dir / filename

    if animated:
        # GIF animado: grava como veio para não perder a animação.
        destination.write_bytes(raw)
        size = len(raw)
    else:
        max_w, max_h = KIND_LIMITS[kind]
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGBA" if "A" in image.mode else "RGB")
        image.thumbnail((max_w, max_h), Image.LANCZOS)
        save_args = {"optimize": True}
        if fmt == "JPEG":
            save_args["quality"] = 88
            if image.mode == "RGBA":
                image = image.convert("RGB")
        image.save(destination, format=fmt, **save_args)
        size = destination.stat().st_size

    record = Upload(
        owner_id=user.id,
        filename=filename,
        mime_type=f"image/{'jpeg' if extension == 'jpg' else extension}",
        size=size,
        kind=kind,
    )
    db.add(record)
    db.commit()

    return {"id": record.id, "url": f"/arquivos/{filename}", "width": image.width, "height": image.height}


@router.get("/arquivos/{name}", include_in_schema=False)
async def serve_file(name: str):
    # Só aceitamos exatamente o formato de nome que nós geramos — isso fecha
    # qualquer tentativa de "../.." no caminho.
    if not SAFE_NAME.match(name):
        raise HTTPException(400, "Nome de arquivo inválido.")

    path: Path = settings.upload_dir / name
    if not path.is_file():
        raise HTTPException(404, "Arquivo não encontrado.")

    return FileResponse(
        path,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
