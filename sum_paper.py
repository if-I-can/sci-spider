import os

def count_pdfs(directory):
    pdf_count = 0
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.lower().endswith('.pdf'):
                pdf_count += 1
    return pdf_count

directory_path = r"C:\Users\17862\Desktop\Large Yellow Croaker"  # 替换为目标目录路径
pdf_count = count_pdfs(directory_path)
print(f'Total number of PDF files: {pdf_count}')