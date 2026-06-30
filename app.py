"""Application web Flask de conversion PDF -> HTML.

Lancement :
    pip install -r requirements.txt
    python app.py
puis ouvrir http://127.0.0.1:5000
"""

from __future__ import annotations

import io
import os

from flask import (
    Flask,
    Response,
    jsonify,
    render_template,
    request,
    send_file,
)
from werkzeug.utils import secure_filename

from converter import VALID_MODES, ConversionError, convert_pdf
from image_converter import (
    DEFAULT_DPI,
    SUPPORTED_IMAGE_EXTS,
    ImageConversionError,
    images_to_pdf,
    images_to_zip,
    pdf_to_images,
)

# Taille maximale d'upload (16 Mo par défaut, configurable via la variable
# d'environnement MAX_UPLOAD_MB).
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "16"))
# Limite de pages pour éviter d'épuiser la mémoire sur de très gros PDF.
MAX_PAGES = int(os.environ.get("MAX_PAGES", "200"))

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024


def _read_upload():
    """Valide et lit le PDF envoyé. Renvoie (octets, nom) ou lève ConversionError."""
    if "file" not in request.files:
        raise ConversionError("Aucun fichier reçu.")
    upload = request.files["file"]
    if not upload or upload.filename == "":
        raise ConversionError("Aucun fichier sélectionné.")

    filename = secure_filename(upload.filename)
    if not filename.lower().endswith(".pdf"):
        raise ConversionError("Le fichier doit être un PDF (.pdf).")

    data = upload.read()
    if not data:
        raise ConversionError("Le fichier est vide.")
    # Signature PDF basique : %PDF
    if not data[:4] == b"%PDF":
        raise ConversionError("Le fichier ne semble pas être un PDF valide.")
    return data, filename


def _resolve_mode() -> str:
    mode = (request.form.get("mode") or request.args.get("mode") or "layout").lower()
    if mode not in VALID_MODES:
        raise ConversionError(f"Mode inconnu : {mode}")
    return mode


@app.route("/")
def index():
    return render_template("index.html", modes=VALID_MODES, max_mb=MAX_UPLOAD_MB)


@app.route("/api/convert", methods=["POST"])
def api_convert():
    """Convertit et renvoie le HTML (prévisualisation) en JSON."""
    try:
        data, filename = _read_upload()
        mode = _resolve_mode()
        result = convert_pdf(
            data,
            mode=mode,
            title=os.path.splitext(filename)[0],
            max_pages=MAX_PAGES,
        )
    except ConversionError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    return jsonify(
        {
            "ok": True,
            "html": result.html,
            "page_count": result.page_count,
            "title": result.title,
            "mode": result.mode,
            "warnings": result.warnings,
        }
    )


@app.route("/api/download", methods=["POST"])
def api_download():
    """Convertit et renvoie directement le fichier HTML en téléchargement."""
    try:
        data, filename = _read_upload()
        mode = _resolve_mode()
        result = convert_pdf(
            data,
            mode=mode,
            title=os.path.splitext(filename)[0],
            max_pages=MAX_PAGES,
        )
    except ConversionError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    out_name = os.path.splitext(filename)[0] + ".html"
    buffer = io.BytesIO(result.html.encode("utf-8"))
    return send_file(
        buffer,
        mimetype="text/html",
        as_attachment=True,
        download_name=out_name,
    )


def _read_pdf_upload():
    """Valide et lit un PDF envoyé (champ ``file``). Renvoie (octets, nom)."""
    if "file" not in request.files:
        raise ImageConversionError("Aucun fichier reçu.")
    upload = request.files["file"]
    if not upload or upload.filename == "":
        raise ImageConversionError("Aucun fichier sélectionné.")
    filename = secure_filename(upload.filename)
    if not filename.lower().endswith(".pdf"):
        raise ImageConversionError("Le fichier doit être un PDF (.pdf).")
    data = upload.read()
    if not data:
        raise ImageConversionError("Le fichier est vide.")
    if data[:4] != b"%PDF":
        raise ImageConversionError("Le fichier ne semble pas être un PDF valide.")
    return data, filename


def _read_image_uploads():
    """Valide et lit les images envoyées (champ ``images``). Renvoie (blobs, types)."""
    uploads = request.files.getlist("images")
    uploads = [u for u in uploads if u and u.filename]
    if not uploads:
        raise ImageConversionError("Aucune image reçue.")

    blobs, types = [], []
    for upload in uploads:
        filename = secure_filename(upload.filename)
        ext = os.path.splitext(filename)[1].lower()
        if ext not in SUPPORTED_IMAGE_EXTS:
            raise ImageConversionError(
                f"Type d'image non supporté : {filename} "
                f"(acceptés : {', '.join(SUPPORTED_IMAGE_EXTS)})"
            )
        data = upload.read()
        if not data:
            raise ImageConversionError(f"Image vide : {filename}")
        blobs.append(data)
        types.append(ext.lstrip("."))
    return blobs, types


@app.route("/api/images-to-pdf", methods=["POST"])
def api_images_to_pdf():
    """Assemble une ou plusieurs images en un seul PDF."""
    try:
        blobs, types = _read_image_uploads()
        pdf_bytes = images_to_pdf(blobs, filetypes=types)
    except ImageConversionError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    buffer = io.BytesIO(pdf_bytes)
    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name="images.pdf",
    )


@app.route("/api/pdf-to-images", methods=["POST"])
def api_pdf_to_images():
    """Rend un PDF en PNG : une seule page -> PNG, sinon archive ZIP."""
    try:
        data, filename = _read_pdf_upload()
        dpi = request.form.get("dpi", type=int) or DEFAULT_DPI
        result = pdf_to_images(data, dpi=dpi, max_pages=MAX_PAGES)
    except ImageConversionError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    stem = os.path.splitext(filename)[0]
    if result.page_count == 1:
        buffer = io.BytesIO(result.images[0])
        return send_file(
            buffer,
            mimetype="image/png",
            as_attachment=True,
            download_name=f"{stem}.png",
        )

    zip_bytes = images_to_zip(result.images, basename=stem)
    buffer = io.BytesIO(zip_bytes)
    return send_file(
        buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"{stem}-png.zip",
    )


@app.errorhandler(413)
def too_large(_err):
    return (
        jsonify(
            {
                "ok": False,
                "error": f"Fichier trop volumineux (max {MAX_UPLOAD_MB} Mo).",
            }
        ),
        413,
    )


@app.route("/health")
def health() -> Response:
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=bool(os.environ.get("DEBUG")))
