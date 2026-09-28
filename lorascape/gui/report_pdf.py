# lorascape/gui/report_pdf.py
"""
CoverageReport를 PDF 파일로 저장함. 새 라이브러리 없이 Qt(QTextDocument + QPrinter)로 HTML을 PDF로 변환함
- 한글은 시스템 글꼴(Malgun Gothic 등)을 씀. QApplication이 떠 있어야 동작함.
"""
from PyQt5.QtCore import QMarginsF
from PyQt5.QtGui import QFont, QPageLayout, QPageSize, QTextDocument
from PyQt5.QtPrintSupport import QPrinter

from lorascape.core.reporting.exporters import build_report_html


def export_report_pdf(report, path: str):
    printer = QPrinter(QPrinter.HighResolution)
    printer.setOutputFormat(QPrinter.PdfFormat)
    printer.setOutputFileName(path)
    # 표가 넓어서 A4 가로로 출력함
    printer.setPageLayout(QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Landscape,
                                      QMarginsF(12, 12, 12, 12), QPageLayout.Millimeter))
    doc = QTextDocument()
    doc.setDefaultFont(QFont("Malgun Gothic", 9))
    doc.setHtml(build_report_html(report))
    doc.print_(printer)
