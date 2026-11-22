#!/usr/bin/env python3
"""Generate the optional physical calibration PDF (requires reportlab)."""
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.graphics.barcode import code128

root = Path(__file__).resolve().parent.parent
output = root / "examples" / "calibration-103x164.pdf"
output.parent.mkdir(exist_ok=True)
dot = 72 / 300
width, height = 1224 * dot, 1941 * dot
c = canvas.Canvas(str(output), pagesize=(width, height), invariant=True)
c.setTitle("QL-1100 Native: 103 x 164 mm calibration")
# Keep all ink inside the documented 1200 x 1822 printable region.
left, bottom = 12 * dot, 60 * dot
right, top = 1212 * dot, (1941 - 59) * dot
c.setLineWidth(0.5)
c.rect(left + 3, bottom + 3, right - left - 6, top - bottom - 6)
c.setFont("Helvetica-Bold", 16)
c.drawString(left + 12, top - 26, "QL-1100 NATIVE")
c.setFont("Helvetica", 10)
for index, text in enumerate([
    "103 x 164 mm roll / 300 dpi",
    "TOP: text should read normally",
    "Check all four border edges and automatic cut.",
    "Print at actual size (100%).",
]):
    c.drawString(left + 12, top - 47 - index * 16, text)
c.setFont("Helvetica-Bold", 12)
c.drawString(left + 12, top - 128, "LEFT")
c.drawRightString(right - 12, top - 156, "RIGHT")
barcode = code128.Code128("QL1100-NATIVE-TEST", barHeight=40, barWidth=0.72, humanReadable=True)
barcode.drawOn(c, left + 12, top - 230)
c.setFont("Helvetica", 9)
c.drawString(left + 12, bottom + 108, "Ruler: 50 mm between the end ticks")
mm = 72 / 25.4
x, y = left + 12, bottom + 85
c.line(x, y, x + 50 * mm, y)
for i in range(0, 51, 5):
    tick = 9 if i % 10 == 0 else 5
    c.line(x + i * mm, y - tick / 2, x + i * mm, y + tick / 2)
    c.drawCentredString(x + i * mm, y - 18, str(i))
c.drawString(left + 12, bottom + 30, "Offline validation is not physical print validation.")
c.showPage()
c.save()
print(output)
