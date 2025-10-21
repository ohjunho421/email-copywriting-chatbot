"""
서비스 소개서 PDF에서 핵심 정보를 추출하여 텍스트로 저장
"""
import PyPDF2
import json
import os

def extract_pdf_text(pdf_path):
    """PDF에서 텍스트 추출"""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                # 서로게이트 페어 제거
                clean_text = page_text.encode('utf-8', 'ignore').decode('utf-8', 'ignore')
                text += clean_text + "\n"
            return text
    except Exception as e:
        print(f"PDF 읽기 오류 ({pdf_path}): {str(e)}")
        return None

def main():
    # PDF 파일 경로
    recon_pdf = "/Users/milo/Desktop/ocean/[포트원]국내커머스채널 재무자동화 솔루션.pdf"
    opi_pdf = "/Users/milo/Desktop/ocean/250502_One Payment Infra 제안서.pdf"
    
    print("🔍 Recon 서비스 소개서 추출 중...")
    recon_text = extract_pdf_text(recon_pdf)
    if recon_text:
        with open('recon_service_info.txt', 'w', encoding='utf-8') as f:
            f.write(recon_text)
        print(f"✅ Recon 정보 저장 완료 ({len(recon_text)} 자)")
    
    print("\n🔍 OPI 서비스 소개서 추출 중...")
    opi_text = extract_pdf_text(opi_pdf)
    if opi_text:
        with open('opi_service_info.txt', 'w', encoding='utf-8') as f:
            f.write(opi_text)
        print(f"✅ OPI 정보 저장 완료 ({len(opi_text)} 자)")
    
    # 요약 정보 생성
    service_info = {
        "recon": {
            "file": recon_pdf,
            "text_length": len(recon_text) if recon_text else 0,
            "extracted": True if recon_text else False
        },
        "opi": {
            "file": opi_pdf,
            "text_length": len(opi_text) if opi_text else 0,
            "extracted": True if opi_text else False
        }
    }
    
    with open('service_info_summary.json', 'w', encoding='utf-8') as f:
        json.dump(service_info, f, ensure_ascii=False, indent=2)
    
    print("\n✅ 모든 서비스 정보 추출 완료!")
    print(f"- recon_service_info.txt")
    print(f"- opi_service_info.txt")
    print(f"- service_info_summary.json")

if __name__ == "__main__":
    main()
