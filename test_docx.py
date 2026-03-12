from docx import Document
doc = Document()
doc.add_paragraph("Hello world, this is a test document.")
doc.save("test.docx")
from src.tools.filesystem import read_file_page
print(read_file_page("test.docx"))
