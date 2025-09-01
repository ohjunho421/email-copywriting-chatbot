#!/usr/bin/env python3
"""
AWS Bedrock 모델 접근 권한 확인 스크립트
"""

import boto3
import os
from dotenv import load_dotenv
from botocore.exceptions import ClientError

load_dotenv()

def check_bedrock_access():
    """Bedrock 모델 접근 권한 확인"""
    try:
        # Bedrock 클라이언트 생성
        bedrock_client = boto3.client(
            'bedrock',
            region_name=os.getenv('AWS_REGION', 'us-east-1'),
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
        )
        
        print("🔍 Bedrock 모델 접근 권한 확인 중...")
        
        # 모델 접근 권한 확인
        response = bedrock_client.list_foundation_models()
        
        # Claude 모델 필터링
        claude_models = []
        for model in response.get('modelSummaries', []):
            model_id = model.get('modelId', '')
            model_name = model.get('modelName', '')
            if 'claude' in model_id.lower():
                claude_models.append({
                    'id': model_id,
                    'name': model_name,
                    'provider': model.get('providerName', ''),
                    'status': model.get('modelLifecycle', {}).get('status', 'UNKNOWN')
                })
        
        if claude_models:
            print(f"\n✅ 접근 가능한 Claude 모델: {len(claude_models)}개")
            for model in claude_models:
                status_emoji = "🟢" if model['status'] == 'ACTIVE' else "🔴"
                print(f"  {status_emoji} {model['name']} ({model['id']})")
                
            # Claude 3.5 Sonnet 확인
            sonnet_models = [m for m in claude_models if '3-5-sonnet' in m['id']]
            if sonnet_models:
                print(f"\n🎯 Claude 3.5 Sonnet 사용 가능!")
                return True
            else:
                print(f"\n⚠️  Claude 3.5 Sonnet 접근 권한 없음")
                print("   AWS 콘솔에서 모델 접근 권한을 요청해주세요.")
                return False
        else:
            print("\n❌ 접근 가능한 Claude 모델이 없습니다.")
            return False
            
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        if error_code == 'AccessDeniedException':
            print("❌ AWS Bedrock 서비스 접근 권한이 없습니다.")
            print("   IAM 사용자에게 bedrock:* 권한을 부여해주세요.")
        else:
            print(f"❌ AWS 오류: {error_code} - {e}")
        return False
    except Exception as e:
        print(f"❌ 예외 오류: {str(e)}")
        return False

def show_model_access_instructions():
    """모델 접근 권한 활성화 방법 안내"""
    print("\n" + "="*60)
    print("📋 Claude 3.5 Sonnet 접근 권한 활성화 방법")
    print("="*60)
    print("1. AWS 콘솔 로그인 (https://console.aws.amazon.com)")
    print("2. 리전을 us-east-1 (버지니아 북부)로 변경")
    print("3. Amazon Bedrock 서비스로 이동")
    print("4. 왼쪽 메뉴에서 'Model access' 클릭")
    print("5. 'Modify model access' 버튼 클릭")
    print("6. Anthropic 섹션에서 'Claude 3.5 Sonnet v2' 체크")
    print("7. 'Submit' 클릭")
    print("8. 승인까지 몇 분 소요될 수 있음")
    print("="*60)

if __name__ == "__main__":
    has_access = check_bedrock_access()
    
    if not has_access:
        show_model_access_instructions()
    else:
        print("\n🚀 Claude 3.5 Sonnet 사용 준비 완료!")