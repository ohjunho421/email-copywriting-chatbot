"""
데이터 필터링 결과를 이메일 마케팅 앱에 연동하는 유틸리티
"""

import pandas as pd
import json
from datetime import datetime
import os

class DataIntegrationUtils:
    """
    주피터 노트북에서 필터링한 데이터를 앱에서 사용할 수 있도록 변환하는 클래스
    """
    
    def __init__(self, csv_path=None):
        self.csv_path = csv_path or '/Users/milo/Desktop/ocean/영중소구간필터링/202508최종취합/서울성남_통신판매사업자_완전통합.csv'
        self.df = None
        
    def load_data(self):
        """원본 데이터 로드"""
        try:
            self.df = pd.read_csv(self.csv_path)
            print(f"✅ 데이터 로드 완료: {len(self.df):,}개 레코드")
            return True
        except Exception as e:
            print(f"❌ 데이터 로드 실패: {e}")
            return False
    
    def get_valid_email_targets(self):
        """유효한 이메일 타겟만 추출"""
        if self.df is None:
            self.load_data()
            
        filtered = self.df[
            (self.df['전자우편'].notna()) & 
            (self.df['전자우편'] != '') &
            (~self.df['전자우편'].str.contains('\\*', na=False)) &
            (self.df['업소상태'] == '정상영업')
        ].copy()
        
        return filtered
    
    def filter_by_business_type(self, business_types=['법인']):
        """법인구분별 필터링"""
        targets = self.get_valid_email_targets()
        return targets[targets['법인구분'].isin(business_types)]
    
    def filter_by_platform(self, platforms=['자체웹사이트']):
        """플랫폼별 필터링"""
        targets = self.get_valid_email_targets()
        
        def categorize_platform(domain):
            if pd.isna(domain) or domain == '':
                return '정보없음'
            
            domain_lower = str(domain).lower()
            
            if 'naver' in domain_lower or '네이버' in domain_lower or 'smartstore' in domain_lower:
                return '네이버'
            elif 'coupang' in domain_lower or '쿠팡' in domain_lower:
                return '쿠팡'
            elif any(platform in domain_lower for platform in ['http', 'www', '.com', '.co.kr']):
                return '자체웹사이트'
            else:
                return '기타플랫폼'
        
        targets['플랫폼분류'] = targets['인터넷도메인'].apply(categorize_platform)
        return targets[targets['플랫폼분류'].isin(platforms)]
    
    def convert_to_app_format(self, filtered_df):
        """
        필터링된 데이터를 앱에서 사용하는 형식으로 변환
        app.py의 기존 컬럼명에 맞춰 변환
        """
        converted_data = []
        
        for _, row in filtered_df.iterrows():
            # 기존 앱에서 사용하는 컬럼명으로 매핑
            company_data = {
                '회사명': row['상호'],
                '대표자명': row['대표자명'],
                '이메일': row['전자우편'],
                '전화번호': row['전화번호'],
                '웹사이트': row['인터넷도메인'],
                '법인구분': row['법인구분'],
                '사업자등록번호': row['사업자등록번호'],
                '지역': row['지역'],
                '신고일자': row['신고일자'],
                '업소상태': row['업소상태']
            }
            converted_data.append(company_data)
        
        return converted_data
    
    def save_filtered_data(self, filtered_df, output_path='filtered_companies.csv'):
        """필터링된 데이터를 CSV로 저장"""
        try:
            filtered_df.to_csv(output_path, index=False, encoding='utf-8-sig')
            print(f"✅ 필터링된 데이터 저장 완료: {output_path}")
            print(f"📊 저장된 레코드 수: {len(filtered_df):,}개")
            return True
        except Exception as e:
            print(f"❌ 데이터 저장 실패: {e}")
            return False
    
    def save_for_app_integration(self, filtered_df, output_path='app_ready_data.json'):
        """앱 연동용 JSON 형식으로 저장"""
        try:
            app_data = self.convert_to_app_format(filtered_df)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(app_data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ 앱 연동용 데이터 저장 완료: {output_path}")
            print(f"📊 저장된 레코드 수: {len(app_data):,}개")
            return True
        except Exception as e:
            print(f"❌ 앱 연동용 데이터 저장 실패: {e}")
            return False
    
    def get_statistics(self, filtered_df):
        """필터링 결과 통계"""
        stats = {
            'total_records': len(filtered_df),
            'business_type_distribution': filtered_df['법인구분'].value_counts().to_dict(),
            'region_distribution': filtered_df['지역'].value_counts().to_dict(),
            'valid_emails': len(filtered_df[filtered_df['전자우편'].notna()]),
            'valid_websites': len(filtered_df[filtered_df['인터넷도메인'].notna()]),
        }
        
        return stats

# 사용 예제 함수들
def example_corporate_filter():
    """법인만 필터링하는 예제"""
    utils = DataIntegrationUtils()
    
    # 법인만 필터링
    corporate_data = utils.filter_by_business_type(['법인'])
    print(f"🏢 법인 데이터: {len(corporate_data):,}개")
    
    # 앱 연동용으로 저장
    utils.save_for_app_integration(corporate_data, 'corporate_targets.json')
    utils.save_filtered_data(corporate_data, 'corporate_targets.csv')
    
    return corporate_data

def example_own_website_filter():
    """자체 웹사이트를 가진 업체만 필터링하는 예제"""
    utils = DataIntegrationUtils()
    
    # 자체 웹사이트를 가진 업체만 필터링
    website_data = utils.filter_by_platform(['자체웹사이트'])
    print(f"🌐 자체 웹사이트 보유 업체: {len(website_data):,}개")
    
    # 앱 연동용으로 저장
    utils.save_for_app_integration(website_data, 'website_owners.json')
    utils.save_filtered_data(website_data, 'website_owners.csv')
    
    return website_data

if __name__ == "__main__":
    # 테스트 실행
    print("🚀 데이터 연동 유틸리티 테스트")
    
    # 법인 필터링 예제
    print("\n1️⃣ 법인 필터링 예제:")
    corporate_data = example_corporate_filter()
    
    # 자체 웹사이트 필터링 예제
    print("\n2️⃣ 자체 웹사이트 필터링 예제:")
    website_data = example_own_website_filter()
    
    print("\n✅ 테스트 완료!")
