"""Validação centralizada dos arquivos enviados ao LOGGERAL."""

from pathlib import Path
from zipfile import BadZipFile, ZipFile

from django.core.exceptions import ValidationError

MIB = 1024 * 1024
MEDIA_LIMIT = 100 * MIB
DOCUMENT_LIMIT = 20 * MIB
IMAGE_LIMIT = 10 * MIB


def _header(upload, size=32):
    position = upload.tell() if hasattr(upload, "tell") else 0
    chunk = upload.read(size)
    if hasattr(upload, "seek"):
        upload.seek(position)
    return bytes(chunk)


def _is_pdf(header):
    return header.startswith(b"%PDF-")


def _is_xls(header):
    return header.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")


def _is_xlsx(upload):
    position = upload.tell() if hasattr(upload, "tell") else 0
    try:
        with ZipFile(upload) as workbook:
            members = set(workbook.namelist())
            return {
                "[Content_Types].xml",
                "xl/workbook.xml",
            }.issubset(members)
    except (BadZipFile, OSError, ValueError):
        return False
    finally:
        if hasattr(upload, "seek"):
            upload.seek(position)


def _is_image(header, extension):
    signatures = {
        ".png": header.startswith(b"\x89PNG\r\n\x1a\n"),
        ".jpg": header.startswith(b"\xff\xd8\xff"),
        ".jpeg": header.startswith(b"\xff\xd8\xff"),
        ".gif": header.startswith((b"GIF87a", b"GIF89a")),
    }
    return signatures.get(extension, False)


def _is_video(header, extension):
    if extension == ".mp4":
        return len(header) >= 12 and header[4:8] == b"ftyp"
    if extension == ".avi":
        return header.startswith(b"RIFF") and header[8:12] == b"AVI "
    if extension == ".mov":
        return len(header) >= 12 and header[4:8] == b"ftyp"
    return False


def validate_pdf_upload(upload, *, limit=DOCUMENT_LIMIT):
    if upload is None:
        return
    extension = Path(upload.name).suffix.lower()
    if extension != ".pdf":
        display_extension = extension.lstrip(".") or "sem extensão"
        raise ValidationError(
            f"A extensão de arquivo “{display_extension}” não é permitida. A extensão permitida é: pdf."
        )
    if not _is_pdf(_header(upload)):
        raise ValidationError("O documento deve ser um PDF válido.")
    if getattr(upload, "size", 0) > limit:
        raise ValidationError(f"O documento deve ter no máximo {limit // MIB} MB.")


def validate_navio_document_upload(upload, *, limit=DOCUMENT_LIMIT):
    """Aceita documentos PDF e planilhas Excel legítimas no cadastro de navios."""
    if upload is None:
        return
    extension = Path(upload.name).suffix.lower()
    if extension not in {".pdf", ".xls", ".xlsx"}:
        display_extension = extension.lstrip(".") or "sem extensão"
        raise ValidationError(
            f"A extensão de arquivo “{display_extension}” não é permitida. "
            "Use PDF, XLS ou XLSX."
        )
    if getattr(upload, "size", 0) > limit:
        raise ValidationError(f"O documento deve ter no máximo {limit // MIB} MB.")

    header = _header(upload)
    is_valid = {
        ".pdf": lambda: _is_pdf(header),
        ".xls": lambda: _is_xls(header),
        ".xlsx": lambda: _is_xlsx(upload),
    }[extension]()
    if not is_valid:
        raise ValidationError(
            "O conteúdo do documento não corresponde a um arquivo PDF, XLS ou XLSX válido."
        )


def validate_media_upload(upload):
    extension = Path(upload.name).suffix.lower()
    header = _header(upload)
    if extension in {".png", ".jpg", ".jpeg", ".gif"}:
        if not _is_image(header, extension):
            raise ValidationError("A imagem enviada não corresponde ao formato do arquivo.")
        limit = IMAGE_LIMIT
    elif extension in {".mp4", ".avi", ".mov"}:
        if not _is_video(header, extension):
            raise ValidationError("O vídeo enviado não corresponde ao formato do arquivo.")
        limit = MEDIA_LIMIT
    else:
        raise ValidationError("Formato não permitido. Use PNG, JPG, GIF, MP4, AVI ou MOV.")
    if getattr(upload, "size", 0) > limit:
        raise ValidationError(f"O arquivo deve ter no máximo {limit // MIB} MB.")


def validate_image_upload(upload):
    if upload is None:
        return
    extension = Path(upload.name).suffix.lower()
    if extension not in {".png", ".jpg", ".jpeg", ".gif"} or not _is_image(_header(upload), extension):
        raise ValidationError("A foto deve ser uma imagem PNG, JPG ou GIF válida.")
    if getattr(upload, "size", 0) > IMAGE_LIMIT:
        raise ValidationError(f"A foto deve ter no máximo {IMAGE_LIMIT // MIB} MB.")


def collect_upload_errors(*, documents=(), media=()):
    errors = []
    for upload in documents:
        try:
            validate_navio_document_upload(upload)
        except ValidationError as exc:
            errors.extend(exc.messages)
    for upload in media:
        try:
            validate_media_upload(upload)
        except ValidationError as exc:
            errors.extend(exc.messages)
    return errors
