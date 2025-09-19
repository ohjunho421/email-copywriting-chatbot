/**
 * 간단한 자동 서버 관리 (더 안정적인 방법)
 */

/**
 * 원클릭 1차메일 발송 (모든 것 자동 처리)
 */
function oneClickBatchSendFirstEmail() {
  try {
    console.log('🚀 원클릭 1차메일 발송 시작');
    
    // 1. 서버 필요성 체크
    const needsServer = checkIfClaudeEmailExists();
    
    if (needsServer) {
      // 2. 서버 시작 안내 및 자동 시작 시도
      const proceed = handleServerStartup();
      if (!proceed) return;
    }
    
    // 3. 발송 진행
    batchSendFirstEmailWithAI();
    
  } catch (error) {
    console.error('원클릭 발송 오류:', error);
    SpreadsheetApp.getUi().alert('오류', `발송 중 오류: ${error.message}`, SpreadsheetApp.getUi().ButtonSet.OK);
  }
}

/**
 * 원클릭 테스트메일 발송
 */
function oneClickSendTestEmail() {
  try {
    console.log('🧪 원클릭 테스트메일 발송 시작');
    
    // 1. 선택된 행 체크
    const needsServer = checkSelectedRowForClaude();
    
    if (needsServer) {
      // 2. 서버 시작 처리
      const proceed = handleServerStartup();
      if (!proceed) return;
    }
    
    // 3. 테스트메일 발송
    sendTestEmailWithAI();
    
  } catch (error) {
    console.error('원클릭 테스트메일 오류:', error);
    SpreadsheetApp.getUi().alert('오류', `테스트메일 발송 중 오류: ${error.message}`, SpreadsheetApp.getUi().ButtonSet.OK);
  }
}

/**
 * Claude 개인화 메일 존재 여부 확인
 */
function checkIfClaudeEmailExists() {
  const sheet = SpreadsheetApp.getActiveSheet();
  const data = sheet.getDataRange().getValues();
  const headers = data[0];
  
  const emailTemplateColumnIndex = headers.indexOf('이메일템플릿형식');
  if (emailTemplateColumnIndex === -1) return false;
  
  for (let i = 1; i < data.length; i++) {
    if (data[i][emailTemplateColumnIndex] === 'claude 개인화 메일') {
      return true;
    }
  }
  return false;
}

/**
 * 선택된 행이 Claude 메일인지 확인
 */
function checkSelectedRowForClaude() {
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
 * 서버 시작 처리 (사용자 친화적)
 */
function handleServerStartup() {
  // 1. 서버 상태 확인
  if (isServerAlreadyRunning()) {
    console.log('✅ 서버가 이미 실행 중');
    return true;
  }
  
  // 2. 사용자에게 서버 시작 안내
  const userChoice = showServerStartupChoice();
  
  if (userChoice === 'auto') {
    // 자동 시작 시도
    return attemptAutoServerStart();
  } else if (userChoice === 'manual') {
    // 수동 시작 가이드
    showManualStartGuide();
    return false;
  } else {
    // 취소
    return false;
  }
}

/**
 * 서버 실행 상태 확인
 */
function isServerAlreadyRunning() {
  try {
    const response = UrlFetchApp.fetch('http://localhost:5001/api/health', {
      method: 'GET',
      muteHttpExceptions: true
    });
    return response.getResponseCode() === 200;
  } catch (error) {
    return false;
  }
}

/**
 * 서버 시작 선택 다이얼로그
 */
function showServerStartupChoice() {
  const ui = SpreadsheetApp.getUi();
  
  const response = ui.alert(
    '🤖 AI 챗봇 서버 필요',
    'Claude 개인화 메일을 위해 Python 서버가 필요합니다.\n\n어떻게 진행하시겠습니까?',
    ui.ButtonSet.YES_NO_CANCEL
  );
  
  if (response === ui.Button.YES) {
    return 'auto'; // 자동 시작
  } else if (response === ui.Button.NO) {
    return 'manual'; // 수동 시작
  } else {
    return 'cancel'; // 취소
  }
}

/**
 * 자동 서버 시작 시도
 */
function attemptAutoServerStart() {
  try {
    console.log('🚀 자동 서버 시작 시도');
    
    // 터미널 명령어 실행 (macOS)
    const script = `
      tell application "Terminal"
        activate
        do script "cd /Users/milo/Desktop/ocean/email-copywriting-chatbot && python3 app.py"
      end tell
    `;
    
    // AppleScript 실행
    Utilities.exec('osascript', ['-e', script]);
    
    // 사용자에게 대기 안내
    SpreadsheetApp.getUi().alert(
      '서버 시작 중',
      '🚀 Python 서버를 시작했습니다.\n\n10-15초 후에 다시 발송 버튼을 눌러주세요.\n터미널 창이 열리면 서버가 시작된 것입니다.',
      SpreadsheetApp.getUi().ButtonSet.OK
    );
    
    return false; // 사용자가 다시 시도하도록
    
  } catch (error) {
    console.error('자동 서버 시작 실패:', error);
    
    SpreadsheetApp.getUi().alert(
      '자동 시작 실패',
      '자동 서버 시작에 실패했습니다.\n수동으로 시작해주세요.',
      SpreadsheetApp.getUi().ButtonSet.OK
    );
    
    showManualStartGuide();
    return false;
  }
}

/**
 * 수동 시작 가이드
 */
function showManualStartGuide() {
  const htmlContent = `
    <div style="padding: 25px; font-family: Arial, sans-serif; line-height: 1.6;">
      <h2 style="color: #4f46e5; margin-bottom: 20px;">🛠️ Python 서버 수동 시작</h2>
      
      <div style="background: #f0f9ff; padding: 15px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #0ea5e9;">
        <p style="margin: 0; color: #0c4a6e;">
          <strong>터미널에서 다음 명령어를 실행하세요:</strong>
        </p>
      </div>
      
      <div style="background: #1f2937; color: #10b981; padding: 15px; border-radius: 8px; font-family: monospace; margin: 15px 0; font-size: 14px;">
cd /Users/milo/Desktop/ocean/email-copywriting-chatbot<br>
python3 app.py
      </div>
      
      <div style="background: #fef3c7; padding: 15px; border-radius: 8px; margin: 20px 0;">
        <h4 style="margin-top: 0; color: #92400e;">📋 단계별 가이드:</h4>
        <ol style="margin: 0; color: #92400e;">
          <li><strong>터미널 열기</strong> (Applications > Utilities > Terminal)</li>
          <li><strong>위 명령어 복사 & 붙여넣기</strong></li>
          <li><strong>Enter 키 누르기</strong></li>
          <li><strong>서버 시작 확인</strong> (http://localhost:5001 메시지 확인)</li>
          <li><strong>다시 발송 버튼 클릭</strong></li>
        </ol>
      </div>
      
      <div style="text-align: center; margin-top: 25px;">
        <button onclick="google.script.host.close()" style="
          padding: 12px 24px;
          background: #4f46e5;
          color: white;
          border: none;
          border-radius: 6px;
          cursor: pointer;
          font-size: 14px;
        ">확인</button>
      </div>
    </div>
  `;
  
  const htmlOutput = HtmlService.createHtmlOutput(htmlContent)
    .setWidth(550)
    .setHeight(450);
  
  SpreadsheetApp.getUi().showModalDialog(htmlOutput, 'Python 서버 시작 가이드');
}

/**
 * 업데이트된 메뉴 (원클릭 버전)
 */
function onOpen() {
  const ui = SpreadsheetApp.getUi();
  
  ui.createMenu('🚀 PortOne AI 메일')
    .addItem('📧 1차메일 발송 (원클릭)', 'oneClickBatchSendFirstEmail')
    .addItem('🧪 테스트메일 (원클릭)', 'oneClickSendTestEmail')
    .addSeparator()
    .addItem('🔍 서버 상태 확인', 'checkCurrentServerStatus')
    .addItem('📖 서버 시작 가이드', 'showManualStartGuide')
    .addToUi();
}

/**
 * 현재 서버 상태 확인
 */
function checkCurrentServerStatus() {
  if (isServerAlreadyRunning()) {
    SpreadsheetApp.getUi().alert(
      '서버 상태', 
      '✅ Python 챗봇 서버가 정상 작동 중입니다!\n\n주소: http://localhost:5001\n상태: 준비 완료', 
      SpreadsheetApp.getUi().ButtonSet.OK
    );
  } else {
    SpreadsheetApp.getUi().alert(
      '서버 상태', 
      '❌ Python 챗봇 서버가 실행되지 않았습니다.\n\n💡 해결 방법:\n1. "📧 1차메일 발송 (원클릭)" 버튼 클릭\n2. 자동 시작 선택\n3. 또는 수동으로 터미널에서 시작', 
      SpreadsheetApp.getUi().ButtonSet.OK
    );
  }
}
