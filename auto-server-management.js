/**
 * 자동 서버 관리 시스템
 * 버튼 클릭 시 서버 자동 시작 및 관리
 */

// 서버 관리 설정
const SERVER_CONFIG = {
  url: 'http://localhost:5001',
  healthEndpoint: '/api/health',
  startCommand: 'python3 app.py',
  serverPath: '/Users/milo/Desktop/ocean/email-copywriting-chatbot',
  maxRetries: 3,
  retryDelay: 2000 // 2초
};

/**
 * 스마트 1차메일 발송 (서버 자동 관리)
 */
function smartBatchSendFirstEmail() {
  try {
    console.log('🚀 스마트 1차메일 발송 시작');
    
    // 1. Claude 개인화 메일 필요성 체크
    const needsServer = checkIfServerNeeded();
    
    if (needsServer) {
      console.log('📡 Claude 개인화 메일 감지 - 서버 시작 중...');
      
      // 2. 서버 자동 시작 및 대기
      const serverReady = ensureServerRunning();
      
      if (!serverReady) {
        showServerStartupError();
        return;
      }
    }
    
    // 3. 실제 발송 진행
    console.log('📧 메일 발송 진행');
    batchSendFirstEmailWithAI();
    
  } catch (error) {
    console.error('스마트 발송 오류:', error);
    SpreadsheetApp.getUi().alert('오류', `발송 중 오류가 발생했습니다: ${error.message}`, SpreadsheetApp.getUi().ButtonSet.OK);
  }
}

/**
 * 스마트 테스트메일 발송 (서버 자동 관리)
 */
function smartSendTestEmail() {
  try {
    console.log('🧪 스마트 테스트메일 발송 시작');
    
    // 선택된 행의 템플릿 타입 확인
    const selectedRowNeedsServer = checkSelectedRowForServer();
    
    if (selectedRowNeedsServer) {
      console.log('📡 Claude 개인화 메일 감지 - 서버 시작 중...');
      
      // 서버 자동 시작 및 대기
      const serverReady = ensureServerRunning();
      
      if (!serverReady) {
        showServerStartupError();
        return;
      }
    }
    
    // 실제 테스트메일 발송
    console.log('📧 테스트메일 발송 진행');
    sendTestEmailWithAI();
    
  } catch (error) {
    console.error('스마트 테스트메일 오류:', error);
    SpreadsheetApp.getUi().alert('오류', `테스트메일 발송 중 오류: ${error.message}`, SpreadsheetApp.getUi().ButtonSet.OK);
  }
}

/**
 * 서버 필요성 체크 (전체 시트)
 */
function checkIfServerNeeded() {
  const sheet = SpreadsheetApp.getActiveSheet();
  const data = sheet.getDataRange().getValues();
  const headers = data[0];
  
  const emailTemplateColumnIndex = headers.indexOf('이메일템플릿형식');
  if (emailTemplateColumnIndex === -1) return false;
  
  // 발송 대상 중 Claude 개인화 메일이 있는지 확인
  const sentColumnIndex = headers.indexOf('1차발송여부');
  
  for (let i = 1; i < data.length; i++) {
    const row = data[i];
    
    // 회사명이 없으면 스킵
    if (!row[0]) continue;
    
    // 이미 발송된 메일은 스킵
    if (sentColumnIndex !== -1 && row[sentColumnIndex]) continue;
    
    // Claude 개인화 메일인지 확인
    if (row[emailTemplateColumnIndex] === 'claude 개인화 메일') {
      return true;
    }
  }
  
  return false;
}

/**
 * 선택된 행의 서버 필요성 체크
 */
function checkSelectedRowForServer() {
  const sheet = SpreadsheetApp.getActiveSheet();
  const selection = sheet.getActiveRange();
  const selectedRow = selection.getRow();
  
  if (selectedRow <= 1) return false;
  
  const data = sheet.getDataRange().getValues();
  const headers = data[0];
  const row = data[selectedRow - 1];
  
  const emailTemplateColumnIndex = headers.indexOf('이메일템플릿형식');
  if (emailTemplateColumnIndex === -1) return false;
  
  return row[emailTemplateColumnIndex] === 'claude 개인화 메일';
}

/**
 * 서버 실행 보장 (자동 시작 + 상태 확인)
 */
function ensureServerRunning() {
  try {
    console.log('🔍 서버 상태 확인 중...');
    
    // 1. 현재 서버 상태 확인
    if (isServerRunning()) {
      console.log('✅ 서버가 이미 실행 중입니다');
      return true;
    }
    
    // 2. 서버 시작 시도
    console.log('🚀 서버 시작 중...');
    showServerStartupProgress();
    
    const startResult = startServerAutomatically();
    
    if (startResult.success) {
      // 3. 서버 준비 대기
      const isReady = waitForServerReady();
      
      if (isReady) {
        console.log('✅ 서버 시작 완료');
        hideServerStartupProgress();
        return true;
      } else {
        console.error('❌ 서버 시작 타임아웃');
        hideServerStartupProgress();
        return false;
      }
    } else {
      console.error('❌ 서버 시작 실패:', startResult.error);
      hideServerStartupProgress();
      return false;
    }
    
  } catch (error) {
    console.error('서버 실행 보장 오류:', error);
    hideServerStartupProgress();
    return false;
  }
}

/**
 * 서버 실행 상태 확인
 */
function isServerRunning() {
  try {
    const response = UrlFetchApp.fetch(SERVER_CONFIG.url + SERVER_CONFIG.healthEndpoint, {
      method: 'GET',
      muteHttpExceptions: true
    });
    
    return response.getResponseCode() === 200;
  } catch (error) {
    return false;
  }
}

/**
 * 서버 자동 시작
 */
function startServerAutomatically() {
  try {
    console.log('📡 Python 서버 자동 시작 시도');
    
    // AppleScript를 사용하여 터미널에서 서버 시작
    const appleScript = `
      tell application "Terminal"
        activate
        set newTab to do script "cd ${SERVER_CONFIG.serverPath} && ${SERVER_CONFIG.startCommand}"
        delay 2
      end tell
    `;
    
    // AppleScript 실행 (macOS에서만 작동)
    const result = Utilities.exec('osascript', ['-e', appleScript]);
    
    return { success: true, message: '서버 시작 명령 실행됨' };
    
  } catch (error) {
    console.error('서버 자동 시작 오류:', error);
    
    // 대안: 사용자에게 수동 시작 안내
    return { 
      success: false, 
      error: '자동 시작 실패 - 수동 시작 필요',
      fallback: true
    };
  }
}

/**
 * 서버 준비 대기
 */
function waitForServerReady() {
  const maxWaitTime = 30000; // 30초
  const checkInterval = 2000; // 2초마다 체크
  const maxAttempts = maxWaitTime / checkInterval;
  
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    console.log(`서버 준비 확인 중... (${attempt}/${maxAttempts})`);
    
    if (isServerRunning()) {
      return true;
    }
    
    // 2초 대기
    Utilities.sleep(checkInterval);
  }
  
  return false;
}

/**
 * 서버 시작 진행 상황 표시
 */
function showServerStartupProgress() {
  const htmlContent = `
    <div style="padding: 30px; text-align: center; font-family: Arial, sans-serif;">
      <div style="margin-bottom: 20px;">
        <div style="
          width: 50px; 
          height: 50px; 
          border: 4px solid #f3f3f3;
          border-top: 4px solid #4f46e5;
          border-radius: 50%;
          animation: spin 1s linear infinite;
          margin: 0 auto 20px;
        "></div>
      </div>
      
      <h2 style="color: #4f46e5; margin-bottom: 15px;">🚀 AI 챗봇 서버 시작 중...</h2>
      <p style="color: #666; margin-bottom: 20px;">
        Claude 개인화 메일을 위해 Python 서버를 시작하고 있습니다.<br>
        잠시만 기다려주세요... (최대 30초)
      </p>
      
      <div style="background: #f8fafc; padding: 15px; border-radius: 8px; margin-top: 20px;">
        <p style="margin: 0; font-size: 14px; color: #374151;">
          💡 <strong>진행 중인 작업:</strong><br>
          1. Python 서버 시작<br>
          2. API 연결 확인<br>
          3. 서비스 준비 완료 대기
        </p>
      </div>
      
      <style>
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      </style>
    </div>
  `;
  
  const htmlOutput = HtmlService.createHtmlOutput(htmlContent)
    .setWidth(400)
    .setHeight(300);
  
  // 전역 변수로 다이얼로그 참조 저장
  PropertiesService.getScriptProperties().setProperty('progressDialog', 'shown');
  SpreadsheetApp.getUi().showModalDialog(htmlOutput, 'AI 서버 시작 중');
}

/**
 * 서버 시작 진행 상황 숨기기
 */
function hideServerStartupProgress() {
  // 다이얼로그 닫기 (자동으로 닫힘)
  PropertiesService.getScriptProperties().deleteProperty('progressDialog');
}

/**
 * 서버 시작 오류 표시
 */
function showServerStartupError() {
  const htmlContent = `
    <div style="padding: 25px; font-family: Arial, sans-serif;">
      <h2 style="color: #dc2626; margin-bottom: 20px;">❌ 서버 시작 실패</h2>
      
      <div style="background: #fee2e2; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
        <p style="margin: 0; color: #991b1b;">
          Python 챗봇 서버를 자동으로 시작할 수 없습니다.<br>
          수동으로 서버를 시작해주세요.
        </p>
      </div>
      
      <h3 style="color: #374151;">🛠️ 수동 시작 방법:</h3>
      
      <div style="background: #1f2937; color: #10b981; padding: 15px; border-radius: 8px; font-family: monospace; margin: 15px 0;">
cd /Users/milo/Desktop/ocean/email-copywriting-chatbot<br>
python3 app.py
      </div>
      
      <div style="background: #dbeafe; padding: 15px; border-radius: 8px; margin: 20px 0;">
        <p style="margin: 0; color: #1e3a8a;">
          💡 <strong>서버 시작 후:</strong><br>
          다시 발송 버튼을 클릭하면 정상적으로 작동합니다.
        </p>
      </div>
      
      <div style="text-align: center; margin-top: 25px;">
        <button onclick="google.script.host.close()" style="
          padding: 12px 24px;
          background: #4f46e5;
          color: white;
          border: none;
          border-radius: 6px;
          cursor: pointer;
        ">확인</button>
      </div>
    </div>
  `;
  
  const htmlOutput = HtmlService.createHtmlOutput(htmlContent)
    .setWidth(500)
    .setHeight(400);
  
  SpreadsheetApp.getUi().showModalDialog(htmlOutput, '서버 시작 필요');
}

/**
 * 업데이트된 메뉴
 */
function onOpen() {
  const ui = SpreadsheetApp.getUi();
  
  ui.createMenu('🚀 PortOne AI 메일')
    .addItem('📧 1차메일 발송 (자동 AI)', 'smartBatchSendFirstEmail')
    .addItem('🧪 테스트메일 (자동 AI)', 'smartSendTestEmail')
    .addSeparator()
    .addItem('🔍 서버 상태 확인', 'checkServerStatus')
    .addItem('⚙️ 서버 수동 시작 가이드', 'showManualServerGuide')
    .addToUi();
}

/**
 * 서버 상태 확인 (단순 체크)
 */
function checkServerStatus() {
  if (isServerRunning()) {
    SpreadsheetApp.getUi().alert(
      '서버 상태', 
      '✅ Python 챗봇 서버가 정상 작동 중입니다.\n주소: http://localhost:5001', 
      SpreadsheetApp.getUi().ButtonSet.OK
    );
  } else {
    SpreadsheetApp.getUi().alert(
      '서버 상태', 
      '❌ Python 챗봇 서버가 실행되지 않았습니다.\n"📧 1차메일 발송 (자동 AI)" 버튼을 누르면 자동으로 시작됩니다.', 
      SpreadsheetApp.getUi().ButtonSet.OK
    );
  }
}

/**
 * 수동 서버 시작 가이드
 */
function showManualServerGuide() {
  showServerStartupError(); // 동일한 가이드 재사용
}
