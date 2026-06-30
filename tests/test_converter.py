"""Tests du module de conversion.

Un petit PDF est généré en mémoire avec PyMuPDF pour ne dépendre
d'aucun fichier externe.
"""

import os
import sys

import fitz  # PyMuPDF
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from converter import (  # noqa: E402
    MODE_LAYOUT,
    MODE_REFLOW,
    MODE_TEXT,
    ConversionError,
    convert_pdf,
)


def _make_pdf(pages_text):
    """Construit un PDF en mémoire et renvoie ses octets."""
    doc = fitz.open()
    for text in pages_text:
        page = doc.new_page()
        page.insert_text((72, 72), text, fontsize=14)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def sample_pdf():
    return _make_pdf(["Bonjour le monde", "Deuxieme page"])


def test_layout_conversion(sample_pdf):
    result = convert_pdf(sample_pdf, mode=MODE_LAYOUT)
    assert result.page_count == 2
    assert result.mode == MODE_LAYOUT
    assert "<!DOCTYPE html>" in result.html
    assert "Bonjour le monde" in result.html
    assert 'data-page="2"' in result.html


def test_reflow_conversion(sample_pdf):
    result = convert_pdf(sample_pdf, mode=MODE_REFLOW)
    assert result.page_count == 2
    assert "Deuxieme page" in result.html


def test_text_conversion(sample_pdf):
    result = convert_pdf(sample_pdf, mode=MODE_TEXT)
    assert "<pre>" in result.html
    assert "Bonjour le monde" in result.html


def test_text_mode_escapes_html():
    data = _make_pdf(["<script>alert(1)</script>"])
    result = convert_pdf(data, mode=MODE_TEXT)
    assert "<script>alert(1)</script>" not in result.html
    assert "&lt;script&gt;" in result.html


def test_invalid_mode(sample_pdf):
    with pytest.raises(ConversionError):
        convert_pdf(sample_pdf, mode="inexistant")


def test_invalid_source_bytes():
    with pytest.raises(ConversionError):
        convert_pdf(b"ceci n'est pas un pdf", mode=MODE_LAYOUT)


def test_missing_file():
    with pytest.raises(ConversionError):
        convert_pdf("/chemin/qui/n/existe/pas.pdf")


def test_custom_title(sample_pdf):
    result = convert_pdf(sample_pdf, mode=MODE_TEXT, title="Mon Titre")
    assert result.title == "Mon Titre"
    assert "<title>Mon Titre</title>" in result.html


def test_max_pages_truncation():
    data = _make_pdf(["p1", "p2", "p3", "p4"])
    result = convert_pdf(data, mode=MODE_TEXT, max_pages=2)
    assert result.page_count == 2
    assert any("tronqué" in w for w in result.warnings)


def test_password_protected_pdf():
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "secret", fontsize=14)
    # Chiffre avec un mot de passe utilisateur non vide.
    data = doc.tobytes(
        encryption=fitz.PDF_ENCRYPT_AES_256,
        user_pw="motdepasse",
        owner_pw="motdepasse",
    )
    doc.close()
    with pytest.raises(ConversionError):
        convert_pdf(data, mode=MODE_TEXT)
