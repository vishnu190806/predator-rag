"""Build a compact mixed-format test corpus with known answers/locations."""
import os
from docx import Document
from pptx import Presentation
from openpyxl import Workbook

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_corpus")
os.makedirs(OUT, exist_ok=True)

# 1. PDF with known page locations (via reportlab if available, else pymupdf)
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    def make_pdf(path):
        c = canvas.Canvas(path, pagesize=letter)
        c.setFont("Helvetica-Bold", 14); c.drawString(72, 750, "Aurora Research Station")
        c.setFont("Helvetica", 11)
        c.drawString(72, 730, "The Aurora Research Station was established in 1998 in northern Norway.")
        c.drawString(72, 715, "Its primary mission is atmospheric plasma observation.")
        c.showPage()
        c.setFont("Helvetica-Bold", 14); c.drawString(72, 750, "Reactor Specifications")
        c.setFont("Helvetica", 11)
        c.drawString(72, 730, "The Mark-IV reactor outputs 42 megawatts at full capacity.")
        c.drawString(72, 715, "Coolant intake temperature must stay below 15 degrees Celsius.")
        c.showPage()
        c.save()
    make_pdf(os.path.join(OUT, "station.pdf"))
    print("pdf ok (reportlab)")
except ImportError:
    import fitz
    doc = fitz.open()
    p = doc.new_page()
    p.insert_text((72, 100), "Aurora Research Station\nThe Aurora Research Station was established in 1998 in northern Norway.\nIts primary mission is atmospheric plasma observation.", fontsize=11)
    p = doc.new_page()
    p.insert_text((72, 100), "Reactor Specifications\nThe Mark-IV reactor outputs 42 megawatts at full capacity.\nCoolant intake temperature must stay below 15 degrees Celsius.", fontsize=11)
    doc.save(os.path.join(OUT, "station.pdf"))
    print("pdf ok (pymupdf)")

# 2. DOCX with headings + facts
doc = Document()
doc.add_heading("Project Zephyr Overview", level=1)
doc.add_paragraph("Project Zephyr is a coastal wind-mapping initiative led by engineer Amara Okafor.")
doc.add_heading("Budget", level=2)
doc.add_paragraph("The approved budget for Project Zephyr is 1.25 million euros across three phases.")
doc.save(os.path.join(OUT, "zephyr.docx"))
print("docx ok")

# 3. PPTX with slide-specific info
prs = Presentation()
s1 = prs.slides.add_slide(prs.slide_layouts[5])
s1.shapes.title.text = "Helios Launch Schedule"
tx = s1.shapes.add_textbox(72, 150, 500, 200).text_frame
tx.text = "The Helios-9 launch window opens on 2027-03-14 from Kourou."
s2 = prs.slides.add_slide(prs.slide_layouts[5])
s2.shapes.title.text = "Payload Manifest"
tx2 = s2.shapes.add_textbox(72, 150, 500, 200).text_frame
tx2.text = "Payload includes the Kestrel-2 spectrometer weighing 85 kilograms."
notes = s2.notes_slide.placeholders[1].text_frame
notes.text = "Speaker note: Kestrel-2 calibration requires cryogenic cooling."
prs.save(os.path.join(OUT, "helios.pptx"))
print("pptx ok")

# 4. XLSX with tabular values
wb = Workbook()
ws = wb.active; ws.title = "Inventory"
ws.append(["sku", "item", "qty", "warehouse"])
ws.append(["SKU-4471", "titanium bolts", 1200, "Rotterdam"])
ws.append(["SKU-4472", "ceramic tiles", 340, "Rotterdam"])
ws2 = wb.create_sheet("Pricing")
ws2.append(["sku", "unit_price_eur"])
ws2.append(["SKU-4471", 4.75])
ws2.append(["SKU-4472", 12.30])
wb.save(os.path.join(OUT, "inventory.xlsx"))
print("xlsx ok")

# 5. CSV
with open(os.path.join(OUT, "crew.csv"), "w", encoding="utf-8") as f:
    f.write("name,role,clearance\nElena Vasquez,commander,level-5\nDario Kim,medic,level-3\n")
print("csv ok")

# 6. Markdown
with open(os.path.join(OUT, "protocol.md"), "w", encoding="utf-8") as f:
    f.write("# Decontamination Protocol\n\n## Steps\n\n1. Seal the airlock (valve sequence A-3).\n2. Flood chamber with argon for 90 seconds.\n3. Verify particulate count below 50 ppm.\n\n## Exception\n\nIf pressure exceeds 110 kPa, abort and vent.\n")
print("md ok")

# 7. Unsupported file
with open(os.path.join(OUT, "notes.exe"), "wb") as f:
    f.write(b"MZ fake binary")
print("unsupported marker ok")
print("corpus dir:", OUT)
