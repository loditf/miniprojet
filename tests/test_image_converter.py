"""Tests des conversions image <-> PDF."""

import os
import sys
import zipfile
import io

import fitz  # PyMuPDF
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from image_converter import (  # noqa: E402
    ImageConversionError,
    images_to_pdf,
    images_to_zip,
    pdf_to_images,
)


def _make_png(width=120, height=80, color=(200, 30, 30)):
    """Génère un PNG uni en mémoire via PyMuPDF."""
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, width, height))
    pix.set_rect(pix.irect, color)
    return pix.tobytes("png")


def _make_pdf(num_pages=2):
    doc = fitz.open()
    for i in range(num_pages):
        page = doc.new_page()
        page.insert_text((72, 72), f"page {i + 1}", fontsize=14)
    data = doc.tobytes()
    doc.close()
    return data


def test_single_image_to_pdf():
    pdf_bytes = images_to_pdf([_make_png()], filetypes=["png"])
    assert pdf_bytes[:4] == b"%PDF"
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    assert doc.page_count == 1
    doc.close()


def test_multiple_images_to_pdf():
    images = [_make_png(color=(10, 10, 200)), _make_png(color=(10, 200, 10))]
    pdf_bytes = images_to_pdf(images, filetypes=["png", "png"])
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    assert doc.page_count == 2
    doc.close()


def test_images_to_pdf_empty_list():
    with pytest.raises(ImageConversionError):
        images_to_pdf([])


def test_images_to_pdf_invalid_image():
    with pytest.raises(ImageConversionError):
        images_to_pdf([b"pas une image"], filetypes=["png"])


def test_pdf_to_images_basic():
    result = pdf_to_images(_make_pdf(3), dpi=100)
    assert result.page_count == 3
    assert result.dpi == 100
    for img in result.images:
        # Signature PNG.
        assert img[:8] == b"\x89PNG\r\n\x1a\n"


def test_pdf_to_images_invalid_dpi():
    with pytest.raises(ImageConversionError):
        pdf_to_images(_make_pdf(1), dpi=5000)


def test_pdf_to_images_not_a_pdf():
    with pytest.raises(ImageConversionError):
        pdf_to_images(b"ceci n'est pas un pdf")


def test_pdf_to_images_max_pages():
    result = pdf_to_images(_make_pdf(5), dpi=72, max_pages=2)
    assert result.page_count == 2
    assert any("tronqué" in w for w in result.warnings)


def test_roundtrip_png_pdf_png():
    """PNG -> PDF -> PNG : la page reste rendable."""
    pdf_bytes = images_to_pdf([_make_png()], filetypes=["png"])
    result = pdf_to_images(pdf_bytes, dpi=72)
    assert result.page_count == 1


def test_images_to_zip():
    images = [_make_png(), _make_png(), _make_png()]
    zip_bytes = images_to_zip(images, basename="test")
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
    assert len(names) == 3
    # Numérotation zéro-paddée pour un tri lexicographique correct.
    assert names[0] == "test-01.png"
    assert sorted(names) == names
