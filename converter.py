"""Cœur de la conversion PDF -> HTML.

Ce module est volontairement indépendant de Flask : il peut être utilisé
directement en bibliothèque ou via l'interface en ligne de commande
(`python converter.py mon.pdf -o mon.html`).

La conversion s'appuie sur PyMuPDF (fitz) qui sait extraire un HTML
positionné, fidèle à la mise en page d'origine, et qui embarque les images
en base64.
"""

from __future__ import annotations

import argparse
import html
import os
from dataclasses import dataclass, field
from typing import List, Optional

try:
    import fitz  # PyMuPDF
except ImportError as exc:  # pragma: no cover - dépendance obligatoire
    raise ImportError(
        "PyMuPDF est requis. Installez-le avec : pip install PyMuPDF"
    ) from exc


# Modes de conversion exposés à l'utilisateur.
MODE_LAYOUT = "layout"   # fidèle à la mise en page (positions absolues)
MODE_REFLOW = "reflow"   # texte qui se réagence (plus accessible/responsive)
MODE_TEXT = "text"       # texte brut enveloppé dans des <pre>
VALID_MODES = (MODE_LAYOUT, MODE_REFLOW, MODE_TEXT)


class ConversionError(Exception):
    """Erreur levée quand un PDF ne peut pas être converti."""


@dataclass
class ConversionResult:
    """Résultat d'une conversion."""

    html: str
    page_count: int
    title: str
    mode: str
    warnings: List[str] = field(default_factory=list)


def _open_document(source) -> "fitz.Document":
    """Ouvre un document depuis un chemin (str) ou des octets (bytes)."""
    try:
        if isinstance(source, (bytes, bytearray)):
            return fitz.open(stream=bytes(source), filetype="pdf")
        if isinstance(source, str):
            if not os.path.exists(source):
                raise ConversionError(f"Fichier introuvable : {source}")
            return fitz.open(source)
        raise ConversionError(
            "Source non supportée : fournissez un chemin (str) ou des octets (bytes)."
        )
    except ConversionError:
        raise
    except Exception as exc:  # PyMuPDF lève des erreurs variées
        raise ConversionError(f"Impossible d'ouvrir le PDF : {exc}") from exc


def _document_title(doc: "fitz.Document", fallback: str) -> str:
    meta_title = (doc.metadata or {}).get("title") if doc.metadata else None
    if meta_title and meta_title.strip():
        return meta_title.strip()
    return fallback


def _wrap_document(body: str, title: str) -> str:
    """Enveloppe le contenu des pages dans un document HTML complet."""
    safe_title = html.escape(title)
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="generator" content="pdf2html-converter">
<title>{safe_title}</title>
<style>
  body {{ margin: 0; background: #525659; font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; }}
  .page {{
    position: relative;
    background: #fff;
    margin: 24px auto;
    box-shadow: 0 2px 12px rgba(0,0,0,.35);
    overflow: hidden;
  }}
  .reflow-page, .text-page {{
    max-width: 820px;
    padding: 48px 56px;
    line-height: 1.5;
  }}
  .text-page pre {{ white-space: pre-wrap; word-wrap: break-word; font-size: 14px; }}
  .page-sep {{ text-align: center; color: #cfcfcf; font-size: 12px; margin: 4px 0 20px; }}
  img {{ max-width: 100%; }}
</style>
</head>
<body>
{body}
</body>
</html>
"""


def _convert_layout(doc: "fitz.Document") -> str:
    """Conversion fidèle : chaque page devient un bloc positionné."""
    parts: List[str] = []
    for index, page in enumerate(doc):
        # get_text("html") produit un fragment avec un <div> positionné
        # et les images embarquées en base64.
        page_html = page.get_text("html")
        parts.append(f'<div class="page" data-page="{index + 1}">')
        parts.append(page_html)
        parts.append("</div>")
        parts.append(f'<div class="page-sep">— page {index + 1} —</div>')
    return "\n".join(parts)


def _convert_reflow(doc: "fitz.Document") -> str:
    """Conversion réagençable : flux XHTML par page, responsive."""
    parts: List[str] = []
    for index, page in enumerate(doc):
        page_html = page.get_text("xhtml")
        parts.append(f'<section class="reflow-page" data-page="{index + 1}">')
        parts.append(page_html)
        parts.append("</section>")
        parts.append(f'<div class="page-sep">— page {index + 1} —</div>')
    return "\n".join(parts)


def _convert_text(doc: "fitz.Document") -> str:
    """Conversion en texte brut, échappé et enveloppé dans des <pre>."""
    parts: List[str] = []
    for index, page in enumerate(doc):
        text = page.get_text("text")
        parts.append(f'<section class="text-page" data-page="{index + 1}">')
        parts.append(f"<pre>{html.escape(text)}</pre>")
        parts.append("</section>")
        parts.append(f'<div class="page-sep">— page {index + 1} —</div>')
    return "\n".join(parts)


_CONVERTERS = {
    MODE_LAYOUT: _convert_layout,
    MODE_REFLOW: _convert_reflow,
    MODE_TEXT: _convert_text,
}


def convert_pdf(
    source,
    *,
    mode: str = MODE_LAYOUT,
    title: Optional[str] = None,
    max_pages: Optional[int] = None,
) -> ConversionResult:
    """Convertit un PDF en document HTML autonome.

    Args:
        source: chemin du fichier (str) ou contenu brut (bytes).
        mode: l'un de ``layout``, ``reflow`` ou ``text``.
        title: titre du document HTML (sinon déduit des métadonnées).
        max_pages: limite optionnelle du nombre de pages converties.

    Returns:
        Un :class:`ConversionResult`.

    Raises:
        ConversionError: si le PDF est invalide ou si le mode est inconnu.
    """
    if mode not in VALID_MODES:
        raise ConversionError(
            f"Mode inconnu : {mode!r}. Modes valides : {', '.join(VALID_MODES)}"
        )

    doc = _open_document(source)
    warnings: List[str] = []
    try:
        if doc.is_encrypted:
            # Essai de déchiffrement avec un mot de passe vide.
            if not doc.authenticate(""):
                raise ConversionError(
                    "PDF protégé par mot de passe : conversion impossible."
                )

        total_pages = doc.page_count
        if total_pages == 0:
            raise ConversionError("Le PDF ne contient aucune page.")

        if max_pages is not None and total_pages > max_pages:
            warnings.append(
                f"PDF tronqué : {max_pages} page(s) converties sur {total_pages}."
            )
            doc.select(range(max_pages))

        fallback_title = "Document converti"
        if isinstance(source, str):
            fallback_title = os.path.splitext(os.path.basename(source))[0]
        resolved_title = title or _document_title(doc, fallback_title)

        body = _CONVERTERS[mode](doc)
        full_html = _wrap_document(body, resolved_title)

        return ConversionResult(
            html=full_html,
            page_count=doc.page_count,
            title=resolved_title,
            mode=mode,
            warnings=warnings,
        )
    finally:
        doc.close()


def _cli(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Convertit un fichier PDF en HTML."
    )
    parser.add_argument("pdf", help="Chemin du fichier PDF à convertir.")
    parser.add_argument(
        "-o",
        "--output",
        help="Fichier HTML de sortie (par défaut : même nom que le PDF).",
    )
    parser.add_argument(
        "-m",
        "--mode",
        choices=VALID_MODES,
        default=MODE_LAYOUT,
        help="Mode de conversion (par défaut : layout).",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Limiter le nombre de pages converties.",
    )
    args = parser.parse_args(argv)

    try:
        result = convert_pdf(args.pdf, mode=args.mode, max_pages=args.max_pages)
    except ConversionError as exc:
        print(f"Erreur : {exc}")
        return 1

    output = args.output or os.path.splitext(args.pdf)[0] + ".html"
    with open(output, "w", encoding="utf-8") as fh:
        fh.write(result.html)

    for warning in result.warnings:
        print(f"Avertissement : {warning}")
    print(f"OK : {result.page_count} page(s) -> {output}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_cli())
