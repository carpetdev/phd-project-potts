import pdfplumber
pdf_path = r'C:\Users\ibata\Downloads\Zakaria_SFB_Mathematics_PhD_2016.pdf'
out_path = r'C:\Users\ibata\Documents\Codex\2026-09-25\im\work\Zakaria_SFB_Mathematics_PhD_2016.txt'
with pdfplumber.open(pdf_path) as pdf:
    with open(out_path, 'w', encoding='utf-8') as f:
        for i, page in enumerate(pdf.pages, start=1):
            f.write(f'\n\n===== PDF PAGE {i} =====\n')
            f.write(page.extract_text() or '')
print(out_path)
