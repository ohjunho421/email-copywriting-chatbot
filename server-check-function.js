/**
 * Apps Script에 추가할 서버 상태 체크 함수
 */

/**
 * 서버 상태 확인 및 자동 안내
 */
function checkServerStatusBeforeSending() {
  const sheet = SpreadsheetApp.getActiveSheet();
  const data = sheet.getDataRange().getValues();
  const headers = data[0];
  
  // F열에서 "claude 개인화 메일"이 있는지 확인
  const emailTemplateColumnIndex = headers.indexOf('이메일템플릿형식');
  let hasClaudeEmails = false;
  
  if (emailTemplateColumnIndex !== -1) {
    for (let i = 1; i < data.length; i++) {
      if (data[i][emailTemplateColumnIndex] === 'claude 개인화 메일') {
        hasClaudeEmails = true;
        break;
      }
    }
  }
  
  if (hasClaudeEmails) {
    // Claude 개인화 메일이 있으면 서버 상태 확인
    const serverStatus = checkChatbotServerStatus();
    
    if (!serverStatus.isRunning) {
      showServerStartGuide();
      return false;
    } else {
      SpreadsheetApp.getUi().alert(
        '서버 연결 확인', 
        '✅ Python 챗봇 서버가 정상 작동 중입니다.\n이제 발송을 진행할 수 있습니다.', 
        SpreadsheetApp.getUi().ButtonSet.OK
      );
      return true;
    }
  } else {
    // Claude 개인화 메일이 없으면 서버 불필요
    SpreadsheetApp.getUi().alert(
      '발송 준비 완료', 
      '📧 기존 템플릿 메일만 있습니다.\n서버 없이 바로 발송 가능합니다.', 
      SpreadsheetApp.getUi().ButtonSet.OK
    );
    return true;
  }
}

/**
 * 챗봇 서버 상태 확인
 */
function checkChatbotServerStatus() {
  try {
    const response = UrlFetchApp.fetch('http://localhost:5001/api/health', {
      method: 'GET',
      muteHttpExceptions: true
    });
    
    if (response.getResponseCode() === 200) {
      const data = JSON.parse(response.getContentText());
      return {
        isRunning: true,
        status: data.status,
        services: data.services
      };
    } else {
      return { isRunning: false, error: 'Server not responding' };
    }
  } catch (error) {
    return { isRunning: false, error: error.message };
  }
}

/**
 * 서버 시작 가이드 표시
 */
function showServerStartGuide() {
  const htmlContent = `
    <div style="padding: 25px; font-family: Arial, sans-serif; line-height: 1.6;">
      <h2 style="color: #dc2626; margin-bottom: 20px;">⚠️ Python 서버 시작 필요</h2>
      
      <div style="background: #fef3c7; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
        <p style="margin: 0; color: #92400e;">
          <strong>Claude 개인화 메일</strong>을 발송하려면 Python 챗봇 서버가 실행되어야 합니다.
        </p>
      </div>
      
      <h3 style="color: #374151;">🚀 서버 시작 방법:</h3>
      
      <div style="background: #f3f4f6; padding: 15px; border-radius: 8px; margin: 15px 0;">
        <h4 style="margin-top: 0; color: #1f2937;">방법 1: 터미널에서 직접 실행</h4>
        <code style="background: #1f2937; color: #10b981; padding: 10px; display: block; border-radius: 4px; font-family: monospace;">
cd /Users/milo/Desktop/ocean/email-copywriting-chatbot<br>
python3 app.py
        </code>
      </div>
      
      <div style="background: #f3f4f6; padding: 15px; border-radius: 8px; margin: 15px 0;">
        <h4 style="margin-top: 0; color: #1f2937;">방법 2: 스크립트 실행</h4>
        <code style="background: #1f2937; color: #10b981; padding: 10px; display: block; border-radius: 4px; font-family: monospace;">
cd /Users/milo/Desktop/ocean/email-copywriting-chatbot<br>
./start_server.sh
        </code>
      </div>
      
      <div style="background: #dbeafe; padding: 15px; border-radius: 8px; margin: 20px 0;">
        <h4 style="margin-top: 0; color: #1e40af;">💡 팁</h4>
        <ul style="margin: 0; color: #1e3a8a;">
          <li>서버는 <strong>http://localhost:5001</strong>에서 실행됩니다</li>
          <li>서버 실행 후 이 창을 닫고 다시 발송해주세요</li>
          <li>기존 템플릿 메일은 서버 없이도 발송 가능합니다</li>
        </ul>
      </div>
      
      <div style="text-align: center; margin-top: 25px;">
        <button onclick="google.script.host.close()" style="
          padding: 12px 24px;
          background: #4f46e5;
          color: white;
          border: none;
          border-radius: 6px;
          font-size: 14px;
          cursor: pointer;
        ">확인</button>
      </div>
    </div>
  `;
  
  const htmlOutput = HtmlService.createHtmlOutput(htmlContent)
    .setWidth(600)
    .setHeight(500);
  
  SpreadsheetApp.getUi().showModalDialog(htmlOutput, '서버 시작 가이드');
}

/**
 * 스마트 발송 함수 (서버 상태 자동 체크)
 */
function smartSendFirstEmail() {
  if (checkServerStatusBeforeSending()) {
    // 서버 상태가 OK이면 발송 진행
    batchSendFirstEmailWithAI();
  }
  // 서버 상태가 안 좋으면 가이드 표시 후 중단
}

/**
 * 메뉴 업데이트 (기존 onOpen 함수에 추가)
 */
function onOpen() {
  const ui = SpreadsheetApp.getUi();
  
  ui.createMenu('🤖 AI 이메일')
    .addItem('🚀 스마트 1차메일 발송', 'smartSendFirstEmail')
    .addItem('🧪 테스트메일 (AI 개인화)', 'sendTestEmailWithAI')
    .addSeparator()
    .addItem('🔍 서버 상태 확인', 'checkServerStatusBeforeSending')
    .addItem('📊 API 연결 테스트', 'testChatbotConnection')
    .addToUi();
}
