/**
 * 기존 Apps Script 프로젝트에 추가할 코드
 * 이 코드를 기존 appsscript-cold-email 프로젝트에 복사해서 사용하세요
 */

// 설정 - 실제 환경에 맞게 수정하세요
const CHATBOT_API_URL = 'http://localhost:5001/api/apps-script-integration';
const CLAUDE_EMAIL_TYPE = 'claude 개인화 메일';

/**
 * 테스트 메일 발송 (AI 개인화 포함)
 * 기존 sendTestEmail 함수를 대체하거나 새로운 함수로 추가
 */
function sendTestEmailWithAI() {
  try {
    const sheet = SpreadsheetApp.getActiveSheet();
    const selection = sheet.getActiveRange();
    const selectedRow = selection.getRow();
    
    if (selectedRow <= 1) {
      SpreadsheetApp.getUi().alert('오류', '테스트할 행을 선택해주세요.', SpreadsheetApp.getUi().ButtonSet.OK);
      return;
    }
    
    const data = sheet.getDataRange().getValues();
    const headers = data[0];
    const row = data[selectedRow - 1];
    
    // F열(이메일템플릿형식) 인덱스 찾기
    const emailTemplateColumnIndex = headers.indexOf('이메일템플릿형식');
    if (emailTemplateColumnIndex === -1) {
      SpreadsheetApp.getUi().alert('오류', '이메일템플릿형식 열을 찾을 수 없습니다.', SpreadsheetApp.getUi().ButtonSet.OK);
      return;
    }
    
    const emailTemplateType = row[emailTemplateColumnIndex];
    const companyName = row[0];
    
    console.log(`테스트 메일 발송: ${companyName}, 템플릿: ${emailTemplateType}`);
    
    if (emailTemplateType === CLAUDE_EMAIL_TYPE) {
      // Claude 개인화 메일 처리
      handleClaudePersonalizedEmailTest(row, headers, selectedRow, sheet);
    } else {
      // 기존 템플릿 메일 처리 - 기존 함수 호출
      sendTestEmail(); // 기존 함수 호출
    }
    
  } catch (error) {
    console.error('테스트 메일 발송 오류:', error);
    SpreadsheetApp.getUi().alert('오류', `테스트 메일 발송 중 오류: ${error.message}`, SpreadsheetApp.getUi().ButtonSet.OK);
  }
}

/**
 * Claude 개인화 메일 테스트 처리
 */
function handleClaudePersonalizedEmailTest(row, headers, rowIndex, sheet) {
  try {
    console.log(`Claude 개인화 메일 테스트 시작: 행 ${rowIndex}`);
    
    // 회사 데이터 추출
    const companyData = {};
    for (let i = 0; i < headers.length; i++) {
      if (row[i]) {
        companyData[headers[i]] = row[i];
      }
    }
    
    console.log('회사 데이터:', companyData);
    
    // Python 챗봇 API 호출
    const response = callChatbotAPI(companyData);
    
    if (response.success) {
      const interfaceUrl = response.interface_url;
      const companyName = companyData['회사명'] || 'Unknown';
      
      console.log(`웹 인터페이스 생성 성공: ${interfaceUrl}`);
      
      // 사용자에게 웹 인터페이스 링크 제공
      showEmailInterfaceDialog(companyName, interfaceUrl);
      
    } else {
      console.error(`Claude 메일 생성 실패: ${response.error}`);
      SpreadsheetApp.getUi().alert('오류', `AI 메일 생성 실패: ${response.error}`, SpreadsheetApp.getUi().ButtonSet.OK);
    }
    
  } catch (error) {
    console.error(`Claude 개인화 메일 처리 오류:`, error);
    SpreadsheetApp.getUi().alert('오류', `처리 중 오류가 발생했습니다: ${error.message}`, SpreadsheetApp.getUi().ButtonSet.OK);
  }
}

/**
 * Python 챗봇 API 호출
 */
function callChatbotAPI(companyData) {
  try {
    console.log('챗봇 API 호출 시작:', CHATBOT_API_URL);
    
    const payload = {
      company_data: companyData
    };
    
    const options = {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      payload: JSON.stringify(payload),
      muteHttpExceptions: true // 오류 응답도 받기 위해
    };
    
    const response = UrlFetchApp.fetch(CHATBOT_API_URL, options);
    const responseCode = response.getResponseCode();
    const responseText = response.getContentText();
    
    console.log(`API 응답 코드: ${responseCode}`);
    console.log(`API 응답 내용: ${responseText}`);
    
    if (responseCode !== 200) {
      throw new Error(`API 호출 실패 (${responseCode}): ${responseText}`);
    }
    
    const responseData = JSON.parse(responseText);
    return responseData;
    
  } catch (error) {
    console.error('챗봇 API 호출 오류:', error);
    return { 
      success: false, 
      error: `API 연결 실패: ${error.message}. Python 서버가 실행 중인지 확인하세요.` 
    };
  }
}

/**
 * 웹 인터페이스 다이얼로그 표시
 */
function showEmailInterfaceDialog(companyName, interfaceUrl) {
  const htmlContent = `
    <div style="padding: 20px; font-family: Arial, sans-serif; text-align: center;">
      <h2 style="color: #4f46e5;">🚀 ${companyName} 개인화 이메일 생성 완료</h2>
      <p style="margin: 15px 0;">4개의 맞춤 문안이 생성되었습니다.</p>
      <p style="margin: 15px 0;">아래 버튼을 클릭하여 문안을 선택하고 편집하세요:</p>
      
      <div style="margin: 25px 0;">
        <a href="${interfaceUrl}" target="_blank" style="
          display: inline-block;
          padding: 15px 30px;
          background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
          color: white;
          text-decoration: none;
          border-radius: 10px;
          font-weight: bold;
          font-size: 16px;
          box-shadow: 0 4px 15px rgba(79, 70, 229, 0.3);
        ">📝 이메일 문안 선택하기</a>
      </div>
      
      <p style="font-size: 12px; color: #666; margin-top: 20px;">
        * 새 창에서 열립니다<br>
        * 문안 선택 후 자동으로 발송됩니다
      </p>
      
      <div style="margin-top: 20px; padding: 15px; background: #f8fafc; border-radius: 8px;">
        <p style="font-size: 14px; color: #374151; margin: 0;">
          <strong>URL:</strong><br>
          <code style="background: white; padding: 5px; border-radius: 4px; font-size: 12px;">${interfaceUrl}</code>
        </p>
      </div>
    </div>
    
    <script>
      // 자동으로 새 창에서 열기
      window.open('${interfaceUrl}', '_blank', 'width=1200,height=800,scrollbars=yes,resizable=yes');
    </script>
  `;
  
  const htmlOutput = HtmlService.createHtmlOutput(htmlContent)
    .setWidth(600)
    .setHeight(400);
  
  SpreadsheetApp.getUi().showModalDialog(htmlOutput, `${companyName} - AI 이메일 문안 선택`);
}

/**
 * 메뉴에 새 함수 추가 (기존 onOpen 함수 수정)
 */
function onOpen() {
  const ui = SpreadsheetApp.getUi();
  
  // 기존 메뉴가 있다면 그대로 두고, AI 기능만 추가
  ui.createMenu('🤖 AI 이메일')
    .addItem('🧪 테스트메일 (AI 개인화)', 'sendTestEmailWithAI')
    .addItem('🚀 1차메일 발송 (AI 개인화)', 'batchSendFirstEmailWithAI')
    .addSeparator()
    .addItem('📊 API 연결 테스트', 'testChatbotConnection')
    .addToUi();
}

/**
 * API 연결 테스트 함수
 */
function testChatbotConnection() {
  try {
    console.log('API 연결 테스트 시작');
    
    const testData = {
      '회사명': '테스트회사',
      '담당자명': '김대표',
      '대표이메일': 'test@example.com'
    };
    
    const response = callChatbotAPI(testData);
    
    if (response.success) {
      SpreadsheetApp.getUi().alert(
        '연결 성공', 
        `Python 챗봇 서버 연결 성공!\n생성된 문안 수: ${response.variations_count || 0}개`, 
        SpreadsheetApp.getUi().ButtonSet.OK
      );
    } else {
      SpreadsheetApp.getUi().alert(
        '연결 실패', 
        `연결 실패: ${response.error}\n\n해결 방법:\n1. Python 서버 실행 확인\n2. URL 설정 확인: ${CHATBOT_API_URL}`, 
        SpreadsheetApp.getUi().ButtonSet.OK
      );
    }
    
  } catch (error) {
    console.error('API 연결 테스트 오류:', error);
    SpreadsheetApp.getUi().alert(
      '테스트 오류', 
      `테스트 중 오류 발생: ${error.message}`, 
      SpreadsheetApp.getUi().ButtonSet.OK
    );
  }
}

/**
 * 1차메일 발송 (AI 개인화 포함) - 배치 처리
 */
function batchSendFirstEmailWithAI() {
  try {
    const sheet = SpreadsheetApp.getActiveSheet();
    const data = sheet.getDataRange().getValues();
    const headers = data[0];
    
    // F열 인덱스 찾기
    const emailTemplateColumnIndex = headers.indexOf('이메일템플릿형식');
    if (emailTemplateColumnIndex === -1) {
      SpreadsheetApp.getUi().alert('오류', '이메일템플릿형식 열을 찾을 수 없습니다.', SpreadsheetApp.getUi().ButtonSet.OK);
      return;
    }
    
    let claudeCount = 0;
    let traditionalCount = 0;
    
    // 각 행 처리
    for (let i = 1; i < data.length; i++) {
      const row = data[i];
      const emailTemplateType = row[emailTemplateColumnIndex];
      
      // 회사명이 없으면 스킵
      if (!row[0]) continue;
      
      // 이미 발송된 메일은 스킵 (1차발송여부 열 확인)
      const sentColumnIndex = headers.indexOf('1차발송여부');
      if (sentColumnIndex !== -1 && row[sentColumnIndex]) continue;
      
      if (emailTemplateType === CLAUDE_EMAIL_TYPE) {
        // Claude 개인화 메일 처리
        handleClaudePersonalizedEmailTest(row, headers, i + 1, sheet);
        claudeCount++;
        
        // 배치 처리 시에는 한 번에 하나씩 처리
        break; // 첫 번째 Claude 메일만 처리하고 중단
      } else {
        // 기존 템플릿 메일 처리
        // 여기서 기존 batchSendFirstEmail 함수 호출
        traditionalCount++;
      }
    }
    
    if (claudeCount > 0) {
      SpreadsheetApp.getUi().alert(
        '처리 완료', 
        `Claude 개인화 메일 ${claudeCount}건 처리 완료\n웹 인터페이스에서 문안을 선택해주세요.`, 
        SpreadsheetApp.getUi().ButtonSet.OK
      );
    } else if (traditionalCount > 0) {
      SpreadsheetApp.getUi().alert(
        '알림', 
        `기존 템플릿 메일 ${traditionalCount}건 발견\n기존 발송 함수를 사용해주세요.`, 
        SpreadsheetApp.getUi().ButtonSet.OK
      );
    } else {
      SpreadsheetApp.getUi().alert(
        '알림', 
        '발송할 메일이 없습니다.', 
        SpreadsheetApp.getUi().ButtonSet.OK
      );
    }
    
  } catch (error) {
    console.error('배치 발송 오류:', error);
    SpreadsheetApp.getUi().alert('오류', `배치 발송 중 오류: ${error.message}`, SpreadsheetApp.getUi().ButtonSet.OK);
  }
}
