#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF 제안서에서 텍스트를 추출하는 스크립트
"""

import pdfplumber
import sys

def extract_text_from_pdf(pdf_path):
    """PDF 파일에서 텍스트 추출"""
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if page_text:
                    text += f"\n\n=== Page {i+1} ===\n"
                    text += page_text
        return text
    except Exception as e:
        return f"Error reading PDF: {str(e)}"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 extract_pdf.py <pdf_file_path>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    print(f"Extracting text from: {pdf_path}")
    print("="*80)
    
    extracted_text = extract_text_from_pdf(pdf_path)
    print(extracted_text)
