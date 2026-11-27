"""Extracción de texto para indexar PDF, Word (.docx) y Excel (.xlsx) (sección 1.2 de ADR-0010).

Antes de agregar `pypdf`/`python-docx`/`openpyxl`, `extraer_texto` devolvía `None` para estos tres
tipos (limitación documentada, no falla silenciosa): un documento PDF/Word/Excel nunca generaba
fragmentos ni aparecía en el chat del asistente, sin importar cuánto se esperara. Estas pruebas
cubren que el texto nativo de cada formato (sin OCR) ahora sí se extrae.
"""
import io

from app.modules.ia.ocr import extraer_texto, extraer_texto_docx, extraer_texto_pdf, extraer_texto_xlsx


def _pdf_con_texto(texto: str) -> bytes:
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(text=texto)
    return bytes(pdf.output())


def _docx_con_texto(texto: str) -> bytes:
    import docx

    documento = docx.Document()
    documento.add_paragraph(texto)
    buffer = io.BytesIO()
    documento.save(buffer)
    return buffer.getvalue()


def _xlsx_con_texto(texto: str) -> bytes:
    import openpyxl

    libro = openpyxl.Workbook()
    libro.active["A1"] = texto
    buffer = io.BytesIO()
    libro.save(buffer)
    return buffer.getvalue()


def test_extraer_texto_pdf_con_capa_de_texto():
    contenido = _pdf_con_texto("Informe medico sintetico de control")
    texto = extraer_texto_pdf(contenido)
    assert "Informe medico sintetico de control" in texto
    # También disponible a través del punto de entrada único por mime_type.
    assert "Informe medico sintetico" in extraer_texto(contenido, "application/pdf")


def test_extraer_texto_docx():
    contenido = _docx_con_texto("Seguimiento psicosocial del menor, visita de octubre")
    texto = extraer_texto_docx(contenido)
    assert "Seguimiento psicosocial del menor, visita de octubre" in texto
    mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert "Seguimiento psicosocial" in extraer_texto(contenido, mime)


def test_extraer_texto_xlsx():
    contenido = _xlsx_con_texto("Inventario de camas: 6 unidades")
    texto = extraer_texto_xlsx(contenido)
    assert "Inventario de camas: 6 unidades" in texto
    mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "Inventario de camas" in extraer_texto(contenido, mime)


def test_extraer_texto_csv_como_texto_plano():
    contenido = "nombre,relacion\nAna,tia\n".encode("utf-8")
    assert extraer_texto(contenido, "text/csv") == contenido.decode("utf-8")


def test_extraer_texto_pdf_sin_capa_de_texto_devuelve_vacio():
    # Un PDF válido pero sin texto (solo estructura): no hay OCR de páginas escaneadas en esta
    # fase (igual que una imagen sin Tesseract instalado) — texto vacío, no una excepción.
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    contenido = bytes(pdf.output())
    assert extraer_texto_pdf(contenido).strip() == ""


def test_extraer_texto_formato_sin_implementar_sigue_devolviendo_none():
    # PowerPoint y Word/Excel antiguos (.doc/.xls) siguen sin extracción: limitación conocida,
    # documentada, no una falla silenciosa inesperada.
    assert extraer_texto(b"contenido cualquiera", "application/vnd.ms-excel") is None
