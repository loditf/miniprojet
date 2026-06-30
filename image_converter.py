"""Conversions images <-> PDF.

Deux opérations principales :

* :func:`images_to_pdf` — assemble une ou plusieurs images (PNG, JPEG…)
  en un seul PDF, une image par page.
* :func:`pdf_to_images` — rend chaque page d'un PDF en image PNG.

Comme :mod:`converter`, ce module est indépendant de Flask et expose une
interface en ligne de commande (``python image_converter.py ...``).
"""

from __future__ import annotations

import argparse
import io
import os
import zipfile
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

try:
    import fitz  # PyMuPDF
except ImportError as exc:  # pragma: no cover - dépendance obligatoire
    raise ImportError(
        "PyMuPDF est requis. Installez-le avec : pip install PyMuPDF"
    ) from exc


# Extensions image acceptées en entrée pour la conversion vers PDF.
SUPPORTED_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff")

# Bornes raisonnables pour le rendu PDF -> PNG.
MIN_DPI = 36
MAX_DPI = 600
DEFAULT_DPI = 150


class ImageConversionError(Exception):
    """Erreur levée lors d'une conversion image <-> PDF."""


@dataclass
class PdfToImagesResult:
    """Résultat d'un rendu PDF -> images PNG."""

    images: List[bytes]          # une entrée PNG par page
    page_count: int
    dpi: int
    warnings: List[str] = field(default_factory=list)


def _looks_like_pdf(data: bytes) -> bool:
    return data[:4] == b"%PDF"


def images_to_pdf(
    images: Sequence[bytes],
    *,
    filetypes: Optional[Sequence[Optional[str]]] = None,
) -> bytes:
    """Assemble des images en un PDF (une image par page).

    Args:
        images: séquence d'images sous forme d'octets.
        filetypes: indices de type optionnels (``"png"``…) alignés sur
            ``images`` ; ``None`` laisse PyMuPDF détecter automatiquement.

    Returns:
        Les octets du PDF résultant.

    Raises:
        ImageConversionError: si la liste est vide ou si une image est invalide.
    """
    if not images:
        raise ImageConversionError("Aucune image fournie.")

    out_pdf = fitz.open()
    try:
        for index, img_bytes in enumerate(images):
            if not img_bytes:
                raise ImageConversionError(f"Image {index + 1} vide.")
            filetype = None
            if filetypes is not None and index < len(filetypes):
                filetype = filetypes[index]
            try:
                img_doc = fitz.open(stream=img_bytes, filetype=filetype)
            except Exception as exc:
                raise ImageConversionError(
                    f"Image {index + 1} illisible : {exc}"
                ) from exc
            try:
                pdf_bytes = img_doc.convert_to_pdf()
            except Exception as exc:
                raise ImageConversionError(
                    f"Image {index + 1} non convertible en PDF : {exc}"
                ) from exc
            finally:
                img_doc.close()

            img_pdf = fitz.open("pdf", pdf_bytes)
            try:
                out_pdf.insert_pdf(img_pdf)
            finally:
                img_pdf.close()

        if out_pdf.page_count == 0:
            raise ImageConversionError("Aucune page générée.")
        return out_pdf.tobytes()
    finally:
        out_pdf.close()


def pdf_to_images(
    source,
    *,
    dpi: int = DEFAULT_DPI,
    max_pages: Optional[int] = None,
) -> PdfToImagesResult:
    """Rend chaque page d'un PDF en image PNG.

    Args:
        source: chemin (str) ou octets (bytes) du PDF.
        dpi: résolution de rendu (borne ``MIN_DPI``..``MAX_DPI``).
        max_pages: limite optionnelle du nombre de pages rendues.

    Returns:
        Un :class:`PdfToImagesResult`.

    Raises:
        ImageConversionError: PDF invalide, protégé ou vide.
    """
    if dpi < MIN_DPI or dpi > MAX_DPI:
        raise ImageConversionError(
            f"DPI hors limites ({MIN_DPI}-{MAX_DPI}) : {dpi}"
        )

    try:
        if isinstance(source, (bytes, bytearray)):
            if not _looks_like_pdf(bytes(source)):
                raise ImageConversionError("Le fichier n'est pas un PDF valide.")
            doc = fitz.open(stream=bytes(source), filetype="pdf")
        elif isinstance(source, str):
            if not os.path.exists(source):
                raise ImageConversionError(f"Fichier introuvable : {source}")
            doc = fitz.open(source)
        else:
            raise ImageConversionError(
                "Source non supportée : fournissez un chemin (str) ou des octets."
            )
    except ImageConversionError:
        raise
    except Exception as exc:
        raise ImageConversionError(f"Impossible d'ouvrir le PDF : {exc}") from exc

    warnings: List[str] = []
    try:
        if doc.is_encrypted and not doc.authenticate(""):
            raise ImageConversionError(
                "PDF protégé par mot de passe : conversion impossible."
            )

        total = doc.page_count
        if total == 0:
            raise ImageConversionError("Le PDF ne contient aucune page.")

        limit = total
        if max_pages is not None and total > max_pages:
            limit = max_pages
            warnings.append(
                f"PDF tronqué : {max_pages} page(s) rendues sur {total}."
            )

        images: List[bytes] = []
        for page in doc.pages(0, limit):
            pix = page.get_pixmap(dpi=dpi)
            images.append(pix.tobytes("png"))

        return PdfToImagesResult(
            images=images,
            page_count=len(images),
            dpi=dpi,
            warnings=warnings,
        )
    finally:
        doc.close()


def images_to_zip(images: Sequence[bytes], *, basename: str = "page") -> bytes:
    """Empaquète des images PNG dans une archive ZIP en mémoire."""
    buffer = io.BytesIO()
    width = max(2, len(str(len(images))))
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for index, img in enumerate(images, start=1):
            zf.writestr(f"{basename}-{index:0{width}d}.png", img)
    return buffer.getvalue()


def _cli(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Conversions image <-> PDF."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p2pdf = sub.add_parser("to-pdf", help="Assembler des images en PDF.")
    p2pdf.add_argument("images", nargs="+", help="Fichiers image (PNG, JPEG…).")
    p2pdf.add_argument("-o", "--output", default="sortie.pdf", help="PDF de sortie.")

    p2png = sub.add_parser("to-png", help="Rendre un PDF en images PNG.")
    p2png.add_argument("pdf", help="Fichier PDF à rendre.")
    p2png.add_argument(
        "-o", "--output-dir", default=".", help="Dossier de sortie."
    )
    p2png.add_argument("--dpi", type=int, default=DEFAULT_DPI, help="Résolution.")
    p2png.add_argument("--max-pages", type=int, default=None)

    args = parser.parse_args(argv)

    try:
        if args.command == "to-pdf":
            blobs, types = [], []
            for path in args.images:
                ext = os.path.splitext(path)[1].lower()
                if ext not in SUPPORTED_IMAGE_EXTS:
                    print(f"Erreur : type d'image non supporté : {path}")
                    return 1
                with open(path, "rb") as fh:
                    blobs.append(fh.read())
                types.append(ext.lstrip("."))
            pdf_bytes = images_to_pdf(blobs, filetypes=types)
            with open(args.output, "wb") as fh:
                fh.write(pdf_bytes)
            print(f"OK : {len(blobs)} image(s) -> {args.output}")
            return 0

        if args.command == "to-png":
            with open(args.pdf, "rb") as fh:
                data = fh.read()
            result = pdf_to_images(data, dpi=args.dpi, max_pages=args.max_pages)
            os.makedirs(args.output_dir, exist_ok=True)
            stem = os.path.splitext(os.path.basename(args.pdf))[0]
            width = max(2, len(str(result.page_count)))
            for i, img in enumerate(result.images, start=1):
                out = os.path.join(args.output_dir, f"{stem}-{i:0{width}d}.png")
                with open(out, "wb") as fh:
                    fh.write(img)
            for w in result.warnings:
                print(f"Avertissement : {w}")
            print(
                f"OK : {result.page_count} page(s) @ {result.dpi} DPI -> "
                f"{args.output_dir}/"
            )
            return 0
    except (ImageConversionError, OSError) as exc:
        print(f"Erreur : {exc}")
        return 1

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_cli())
