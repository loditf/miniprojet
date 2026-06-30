"""Tests de l'éditeur PDF."""

import os
import sys

import fitz  # PyMuPDF
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pdf_editor  # noqa: E402
from pdf_editor import PdfEditError  # noqa: E402


def _make_pdf(num_pages=3):
    doc = fitz.open()
    for i in range(num_pages):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {i + 1}", fontsize=18)
    data = doc.tobytes()
    doc.close()
    return data


def _make_form_pdf():
    doc = fitz.open()
    page = doc.new_page()
    widget = fitz.Widget()
    widget.field_name = "nom"
    widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
    widget.rect = fitz.Rect(72, 72, 272, 96)
    widget.field_value = ""
    page.add_widget(widget)
    data = doc.tobytes()
    doc.close()
    return data


def test_inspect_returns_thumbnails():
    info = pdf_editor.inspect(_make_pdf(3))
    assert info.page_count == 3
    assert len(info.pages) == 3
    assert all(p.thumbnail for p in info.pages)
    assert info.pages[0].width > 0 and info.pages[0].height > 0


def test_inspect_detects_form_fields():
    info = pdf_editor.inspect(_make_form_pdf())
    names = [f.name for f in info.fields]
    assert "nom" in names


def test_inspect_rejects_non_pdf():
    with pytest.raises(PdfEditError):
        pdf_editor.inspect(b"pas un pdf")


def test_inspect_max_pages():
    info = pdf_editor.inspect(_make_pdf(5), max_pages=2)
    assert len(info.pages) == 2
    assert info.page_count == 5
    assert info.warnings


def test_edit_reorder_and_delete():
    # Garder page 3 puis page 1 (supprime la page 2, inverse l'ordre).
    spec = {"pages": [{"src": 2}, {"src": 0}]}
    out = pdf_editor.edit(_make_pdf(3), spec)
    doc = fitz.open(stream=out, filetype="pdf")
    assert doc.page_count == 2
    assert "Page 3" in doc[0].get_text()
    assert "Page 1" in doc[1].get_text()
    doc.close()


def test_edit_rotation():
    spec = {"pages": [{"src": 0, "rotate": 90}]}
    out = pdf_editor.edit(_make_pdf(1), spec)
    doc = fitz.open(stream=out, filetype="pdf")
    assert doc[0].rotation == 90
    doc.close()


def test_edit_text_overlay():
    spec = {
        "overlays": [
            {"page": 0, "text": "FILIGRANE", "x": 0.2, "y": 0.4,
             "size": 30, "color": "#ff0000", "opacity": 0.3, "rotate": 45}
        ]
    }
    out = pdf_editor.edit(_make_pdf(1), spec)
    doc = fitz.open(stream=out, filetype="pdf")
    assert "FILIGRANE" in doc[0].get_text()
    doc.close()


def test_edit_overlay_invalid_page():
    spec = {"overlays": [{"page": 9, "text": "x"}]}
    with pytest.raises(PdfEditError):
        pdf_editor.edit(_make_pdf(1), spec)


def test_edit_invalid_source_page():
    with pytest.raises(PdfEditError):
        pdf_editor.edit(_make_pdf(2), {"pages": [{"src": 7}]})


def test_edit_empty_page_selection():
    with pytest.raises(PdfEditError):
        pdf_editor.edit(_make_pdf(2), {"pages": []})


def test_edit_fill_form_field():
    out = pdf_editor.edit(_make_form_pdf(), {"fields": {"nom": "Dupont"}})
    doc = fitz.open(stream=out, filetype="pdf")
    values = [w.field_value for page in doc for w in (page.widgets() or [])]
    doc.close()
    assert "Dupont" in values


def test_edit_append_merge():
    spec = {"pages": [{"src": 0}]}
    out = pdf_editor.edit(_make_pdf(2), spec, appended=[_make_pdf(3)])
    doc = fitz.open(stream=out, filetype="pdf")
    assert doc.page_count == 1 + 3
    doc.close()


def test_edit_invalid_color():
    spec = {"overlays": [{"page": 0, "text": "x", "color": "pas-une-couleur"}]}
    with pytest.raises(PdfEditError):
        pdf_editor.edit(_make_pdf(1), spec)


def test_merge_multiple():
    out = pdf_editor.merge([_make_pdf(2), _make_pdf(3)])
    doc = fitz.open(stream=out, filetype="pdf")
    assert doc.page_count == 5
    doc.close()


def test_merge_requires_input():
    with pytest.raises(PdfEditError):
        pdf_editor.merge([])
