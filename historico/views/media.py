import mimetypes
import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import SuspiciousFileOperation
from django.http import FileResponse, Http404, HttpResponse, StreamingHttpResponse
from django.utils._os import safe_join
from django.utils.http import content_disposition_header
from django.views.decorators.clickjacking import xframe_options_sameorigin

from estoque.models import Certificacao, Equipamento

from ..models import DocumentoNavio, FotoVideoNavio
from ..permissions import is_manager


def _equipment_is_visible(user, equipment):
    # Materiais e certificados são documentos operacionais compartilhados na
    # intranet. A autenticação continua obrigatória; somente a edição permanece
    # limitada ao autor ou à gestão.
    return user.is_authenticated


def _authorized_reference(user, relative_path):
    media = FotoVideoNavio.objects.select_related("navio").filter(arquivo=relative_path).first()
    if media:
        return is_manager(user) or media.navio.criado_por_id == user.id
    document = DocumentoNavio.objects.select_related("navio").filter(arquivo=relative_path).first()
    if document:
        return is_manager(user) or document.navio.criado_por_id == user.id

    equipment = Equipamento.objects.filter(foto=relative_path).first()
    if equipment and _equipment_is_visible(user, equipment):
        return True
    equipment = Equipamento.objects.filter(qrcode=relative_path).first()
    if equipment and _equipment_is_visible(user, equipment):
        return True
    certificate = Certificacao.objects.select_related("equipamento").filter(anexo=relative_path).first()
    return bool(certificate and _equipment_is_visible(user, certificate.equipamento))


@login_required
@xframe_options_sameorigin
def protected_media(request, path):
    relative_path = Path(path).as_posix().lstrip("/")
    if not relative_path or not _authorized_reference(request.user, relative_path):
        raise Http404
    try:
        absolute_path = Path(safe_join(settings.MEDIA_ROOT, relative_path))
    except SuspiciousFileOperation as exc:
        raise Http404 from exc
    if not absolute_path.is_file():
        raise Http404

    content_type, _ = mimetypes.guess_type(absolute_path.name)
    content_type = content_type or "application/octet-stream"
    range_header = request.headers.get("Range", "").strip()
    if range_header:
        response = _partial_file_response(absolute_path, content_type, range_header)
    else:
        response = FileResponse(
            absolute_path.open("rb"),
            content_type=content_type,
            as_attachment=False,
            filename=absolute_path.name,
        )
        response["Accept-Ranges"] = "bytes"
    response["Cache-Control"] = "private, max-age=300"
    return response


def _partial_file_response(path, content_type, range_header):
    size = path.stat().st_size
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header)
    if not match or not any(match.groups()) or size == 0:
        return _range_not_satisfiable(size)

    start_text, end_text = match.groups()
    if start_text:
        start = int(start_text)
        end = int(end_text) if end_text else size - 1
    else:
        suffix_length = int(end_text)
        if suffix_length <= 0:
            return _range_not_satisfiable(size)
        start = max(0, size - suffix_length)
        end = size - 1

    if start >= size or start > end:
        return _range_not_satisfiable(size)
    end = min(end, size - 1)
    length = end - start + 1
    response = StreamingHttpResponse(
        _file_range(path, start, length),
        status=206,
        content_type=content_type,
    )
    response["Content-Length"] = str(length)
    response["Content-Range"] = f"bytes {start}-{end}/{size}"
    response["Accept-Ranges"] = "bytes"
    response["Content-Disposition"] = content_disposition_header(False, path.name)
    return response


def _range_not_satisfiable(size):
    response = HttpResponse(status=416)
    response["Content-Range"] = f"bytes */{size}"
    response["Accept-Ranges"] = "bytes"
    return response


def _file_range(path, start, length, chunk_size=64 * 1024):
    with path.open("rb") as stream:
        stream.seek(start)
        remaining = length
        while remaining > 0:
            chunk = stream.read(min(chunk_size, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk
