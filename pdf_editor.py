"""Éditeur PDF simple, au niveau des pages.

Conçu pour un usage « sans état » : le serveur ne conserve rien. Le client
récupère des vignettes des pages, construit une description des opérations
voulues (ordre, rotation, suppression, surimpressions de texte, valeurs de
champs de formulaire), puis renvoie le PDF d'origine accompagné de cette
description pour obtenir le PDF édité.

Toutes les opérations s'appuient sur PyMuPDF (fitz).
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

try:
    import fitz  # PyMuPDF
except ImportError as exc:  # pragma: no cover - dépendance obligatoire
    raise ImportError(
        "PyMuPDF est requis. Installez-le avec : pip install PyMuPDF"
    ) from exc


# Résolution des vignettes affichées dans l'éditeur (volontairement basse).
THUMBNAIL_DPI = 70
MIN_FONT_SIZE = 6
MAX_FONT_SIZE = 144


class PdfEditError(Exception):
    """Erreur levée lors d'une opération d'édition."""


@dataclass
class PageInfo:
    index: int
    width: float          # largeur en points (rotation appliquée)
    height: float         # hauteur en points (rotation appliquée)
    rotation: int         # rotation d'origine de la page
    thumbnail: str        # PNG encodé en base64 (data-URI sans préfixe)


@dataclass
class FieldInfo:
    name: str
    type: str
    value: str
    page_index: int


@dataclass
class DocumentInfo:
    page_count: int
    pages: List[PageInfo] = field(default_factory=list)
    fields: List[FieldInfo] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def _open(source, *, allow_path: bool = True) -> "fitz.Document":
    try:
        if isinstance(source, (bytes, bytearray)):
            data = bytes(source)
            if data[:4] != b"%PDF":
                raise PdfEditError("Le fichier n'est pas un PDF valide.")
            doc = fitz.open(stream=data, filetype="pdf")
        elif allow_path and isinstance(source, str):
            if not os.path.exists(source):
                raise PdfEditError(f"Fichier introuvable : {source}")
            doc = fitz.open(source)
        else:
            raise PdfEditError("Source non supportée.")
    except PdfEditError:
        raise
    except Exception as exc:
        raise PdfEditError(f"Impossible d'ouvrir le PDF : {exc}") from exc

    if doc.is_encrypted and not doc.authenticate(""):
        doc.close()
        raise PdfEditError("PDF protégé par mot de passe : édition impossible.")
    return doc


_WIDGET_TYPE_NAMES = {
    getattr(fitz, "PDF_WIDGET_TYPE_TEXT", 1): "text",
    getattr(fitz, "PDF_WIDGET_TYPE_CHECKBOX", 2): "checkbox",
    getattr(fitz, "PDF_WIDGET_TYPE_COMBOBOX", 4): "combobox",
    getattr(fitz, "PDF_WIDGET_TYPE_LISTBOX", 5): "listbox",
}


def inspect(source, *, max_pages: Optional[int] = None) -> DocumentInfo:
    """Renvoie vignettes et champs de formulaire pour alimenter l'éditeur."""
    doc = _open(source)
    warnings: List[str] = []
    try:
        total = doc.page_count
        if total == 0:
            raise PdfEditError("Le PDF ne contient aucune page.")
        limit = total
        if max_pages is not None and total > max_pages:
            limit = max_pages
            warnings.append(
                f"Aperçu limité aux {max_pages} premières pages sur {total}."
            )

        pages: List[PageInfo] = []
        fields: List[FieldInfo] = []
        for index in range(limit):
            page = doc[index]
            pix = page.get_pixmap(dpi=THUMBNAIL_DPI)
            thumb = base64.b64encode(pix.tobytes("png")).decode("ascii")
            rect = page.rect
            pages.append(
                PageInfo(
                    index=index,
                    width=round(rect.width, 1),
                    height=round(rect.height, 1),
                    rotation=page.rotation,
                    thumbnail=thumb,
                )
            )
            for widget in page.widgets() or []:
                fields.append(
                    FieldInfo(
                        name=widget.field_name or "",
                        type=_WIDGET_TYPE_NAMES.get(widget.field_type, "text"),
                        value=widget.field_value or "",
                        page_index=index,
                    )
                )

        return DocumentInfo(
            page_count=total,
            pages=pages,
            fields=fields,
            warnings=warnings,
        )
    finally:
        doc.close()


def _hex_to_rgb(value: str) -> tuple:
    value = (value or "#000000").lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    if len(value) != 6:
        raise PdfEditError(f"Couleur invalide : {value}")
    try:
        r, g, b = (int(value[i : i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError as exc:
        raise PdfEditError(f"Couleur invalide : {value}") from exc
    return (r, g, b)


def _apply_fields(doc: "fitz.Document", values: Dict[str, str]) -> None:
    """Renseigne les champs de formulaire existants par leur nom."""
    if not values:
        return
    remaining = dict(values)
    for page in doc:
        for widget in page.widgets() or []:
            name = widget.field_name
            if name in remaining:
                try:
                    widget.field_value = str(remaining[name])
                    widget.update()
                except Exception as exc:
                    raise PdfEditError(
                        f"Impossible de remplir le champ « {name} » : {exc}"
                    ) from exc


def _apply_overlay(page: "fitz.Page", overlay: dict) -> None:
    """Surimpose un texte (ou filigrane) sur une page."""
    text = str(overlay.get("text", "")).strip()
    if not text:
        return
    size = float(overlay.get("size", 18))
    size = max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, size))
    color = _hex_to_rgb(overlay.get("color", "#000000"))
    opacity = float(overlay.get("opacity", 1.0))
    opacity = max(0.05, min(1.0, opacity))
    rotate = int(overlay.get("rotate", 0)) % 360

    rect = page.rect
    # Position : pourcentages (0..1) de la page, sinon coin haut-gauche.
    x = float(overlay.get("x", 0.1)) * rect.width
    y = float(overlay.get("y", 0.1)) * rect.height
    point = fitz.Point(x, y)

    morph = None
    if rotate:
        matrix = fitz.Matrix(rotate)
        morph = (point, matrix)

    try:
        page.insert_text(
            point,
            text,
            fontsize=size,
            color=color,
            fill_opacity=opacity,
            morph=morph,
            render_mode=0,
        )
    except Exception as exc:
        raise PdfEditError(f"Échec de la surimpression de texte : {exc}") from exc


def edit(
    source,
    spec: dict,
    *,
    appended: Optional[Sequence[bytes]] = None,
) -> bytes:
    """Applique les opérations décrites par ``spec`` et renvoie le PDF édité.

    Format de ``spec`` (toutes les clés sont optionnelles) ::

        {
          "fields":   {"nom": "Dupont", ...},     # champs de formulaire
          "overlays": [{"page": 0, "text": "...", # surimpressions de texte
                        "x": 0.1, "y": 0.1, "size": 18,
                        "color": "#ff0000", "opacity": 0.4, "rotate": 45}],
          "pages":    [{"src": 0, "rotate": 90},  # sélection / ordre / rotation
                       {"src": 2}]                # (pages absentes = supprimées)
        }

    ``appended`` : PDF supplémentaires à ajouter à la fin (fusion).
    """
    doc = _open(source)
    try:
        # 1) Champs de formulaire (référencés sur le document d'origine).
        _apply_fields(doc, spec.get("fields") or {})

        # 2) Surimpressions de texte (sur les index de pages d'origine).
        for overlay in spec.get("overlays") or []:
            page_index = int(overlay.get("page", 0))
            if 0 <= page_index < doc.page_count:
                _apply_overlay(doc[page_index], overlay)
            else:
                raise PdfEditError(
                    f"Surimpression sur une page inexistante : {page_index}"
                )

        # 3) Sélection / réordonnancement / rotation des pages.
        page_specs = spec.get("pages")
        if page_specs is not None:
            if not page_specs:
                raise PdfEditError("Au moins une page doit être conservée.")
            out = fitz.open()
            try:
                for item in page_specs:
                    src = int(item.get("src"))
                    if not (0 <= src < doc.page_count):
                        raise PdfEditError(f"Page source invalide : {src}")
                    out.insert_pdf(doc, from_page=src, to_page=src)
                    new_page = out[out.page_count - 1]
                    rotate = int(item.get("rotate", 0)) % 360
                    if rotate:
                        # Rotation cumulée avec l'orientation d'origine.
                        new_page.set_rotation((new_page.rotation + rotate) % 360)
                result_doc = out
                close_after = [out]
            finally:
                pass
        else:
            result_doc = doc
            close_after = []

        # 4) Fusion : ajout des PDF supplémentaires à la fin.
        for extra_bytes in appended or []:
            extra = _open(extra_bytes, allow_path=False)
            try:
                result_doc.insert_pdf(extra)
            finally:
                extra.close()

        if result_doc.page_count == 0:
            raise PdfEditError("Le document résultant est vide.")

        output = result_doc.tobytes(garbage=3, deflate=True)
        for d in close_after:
            d.close()
        return output
    finally:
        doc.close()


def merge(sources: Sequence[bytes]) -> bytes:
    """Fusionne plusieurs PDF en un seul, dans l'ordre fourni."""
    if not sources:
        raise PdfEditError("Aucun PDF à fusionner.")
    out = fitz.open()
    try:
        for index, data in enumerate(sources):
            part = _open(data, allow_path=False)
            try:
                out.insert_pdf(part)
            except Exception as exc:
                raise PdfEditError(
                    f"PDF {index + 1} non fusionnable : {exc}"
                ) from exc
            finally:
                part.close()
        if out.page_count == 0:
            raise PdfEditError("Aucune page à fusionner.")
        return out.tobytes(garbage=3, deflate=True)
    finally:
        out.close()
