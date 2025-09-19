/**
 * 즉시 적용 가능한 통합 코드
 * Google Apps Script 편집기에서 새 파일로 추가하세요
 */

// 설정
const CHATBOT_URL = 'http://localhost:5001/api/apps-script-integration';
const CLAUDE_TYPE = 'claude 개인화 메일';

/**
 * 기존 sendTestEmail 함수를 오버라이드
 * (기존 함수 이름을 sendTestEmailOriginal로 변경 후 이 코드 추가)
 */
function sendTestEmail() {
  try {
    console.log('🔄 새로운 테스트메일 함수 실행');
    
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
    
    // F열 확인
    const templateColumnIndex = headers.indexOf('이메일템플릿형식');
    let templateType = '';
    
    if (templateColumnIndex !== -1) {
      templateType = row[templateColumnIndex] || '';
    }
    
    const companyName = row[0];
    console.log(`테스트메일: ${companyName}, 템플릿: "${templateType}"`);
    
    // Claude 개인화 메일인지 확인
    if (templateType === CLAUDE_TYPE) {
      console.log('🤖 Claude 개인화 메일 감지 - 챗봇 실행');
      handleClaudeEmail(row, headers, selectedRow);
    } else {
      console.log('📧 기존 템플릿 - 원래 로직 실행');
      // 기존 로직 실행 (원래 sendTestEmail 내용)
      handleOriginalTestEmail(row, headers, selectedRow);
    }
    
  } catch (error) {
    console.error('테스트메일 오류:', error);
    SpreadsheetApp.getUi().alert('오류', `테스트메일 오류: ${error.message}`, SpreadsheetApp.getUi().ButtonSet.OK);
  }
}

/**
 * Claude 개인화 메일 처리
 */
function handleClaudeEmail(row, headers, rowIndex) {
  try {
    // 1. 서버 상태 확인
    if (!checkServer()) {
      const startServer = SpreadsheetApp.getUi().alert(
        '서버 필요',
        'Claude 개인화 메일을 위해 Python 서버가 필요합니다.\n\n자동으로 시작하시겠습니까?',
        SpreadsheetApp.getUi().ButtonSet.YES_NO
      );
      
      if (startServer === SpreadsheetApp.getUi().Button.YES) {
        startPythonServer();
        SpreadsheetApp.getUi().alert(
          '서버 시작',
          '🚀 서버를 시작했습니다.\n15초 후에 다시 테스트메일 버튼을 눌러주세요.',
          SpreadsheetApp.getUi().ButtonSet.OK
        );
        return;
      } else {
        showServerGuide();
        return;
      }
    }
    
    // 2. 회사 데이터 추출
    const companyData = {};
    for (let i = 0; i < headers.length; i++) {
      if (row[i]) {
        companyData[headers[i]] = row[i];
      }
    }
    
    // 3. 챗봇 API 호출
    const response = callChatbot(companyData);
    
    if (response.success) {
      const companyName = companyData['회사명'] || 'Unknown';
      showWebInterface(companyName, response.interface_url);
    } else {
      SpreadsheetApp.getUi().alert('오류', `AI 메일 생성 실패: ${response.error}`, SpreadsheetApp.getUi().ButtonSet.OK);
    }
    
  } catch (error) {
    console.error('Claude 메일 처리 오류:', error);
    SpreadsheetApp.getUi().alert('오류', `처리 오류: ${error.message}`, SpreadsheetApp.getUi().ButtonSet.OK);
  }
}

/**
 * 기존 테스트메일 처리 (원래 로직)
 */
function handleOriginalTestEmail(row, headers, rowIndex) {
  try {
    // 여기에 기존 sendTestEmail 함수의 내용을 복사
    // 또는 기존 함수를 sendTestEmailOriginal로 이름 변경했다면:
    if (typeof sendTestEmailOriginal === 'function') {
      sendTestEmailOriginal();
    } else {
      // 간단한 기본 테스트메일
      const companyName = row[0];
      const email = row[headers.indexOf('대표이메일')] || row[headers.indexOf('이메일')];
      
      if (email) {
        const subject = `[PortOne] ${companyName} 담당자님께 전달 부탁드립니다`;
        const body = `안녕하세요, ${companyName} 담당자님.\n\nPortOne 테스트메일입니다.\n\n감사합니다.`;
        
        GmailApp.sendEmail(email, subject, body);
        SpreadsheetApp.getUi().alert('발송 완료', `${companyName}에게 테스트메일 발송 완료`, SpreadsheetApp.getUi().ButtonSet.OK);
      } else {
        SpreadsheetApp.getUi().alert('오류', '이메일 주소가 없습니다.', SpreadsheetApp.getUi().ButtonSet.OK);
      }
    }
  } catch (error) {
    console.error('기존 테스트메일 오류:', error);
  }
}

/**
 * 서버 상태 확인
 */
function checkServer() {
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
 * Python 서버 시작
 */
function startPythonServer() {
  try {
    const script = `
      tell application "Terminal"
        activate
        do script "cd /Users/milo/Desktop/ocean/email-copywriting-chatbot && python3 app.py"
      end tell
    `;
    Utilities.exec('osascript', ['-e', script]);
  } catch (error) {
    console.error('서버 시작 실패:', error);
  }
}

/**
 * 챗봇 API 호출
 */
function callChatbot(companyData) {
  try {
    const options = {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      payload: JSON.stringify({ company_data: companyData }),
      muteHttpExceptions: true
    };
    
    const response = UrlFetchApp.fetch(CHATBOT_URL, options);
    const code = response.getResponseCode();
    
    if (code !== 200) {
      return { success: false, error: `서버 오류 (${code})` };
    }
    
    return JSON.parse(response.getContentText());
  } catch (error) {
    return { success: false, error: `연결 실패: ${error.message}` };
  }
}

/**
 * 웹 인터페이스 표시
 */
function showWebInterface(companyName, url) {
  const html = `
    <div style="padding: 30px; text-align: center; font-family: Arial, sans-serif;">
      <h2 style="color: #4f46e5;">🤖 ${companyName} AI 메일 생성 완료!</h2>
      <p style="margin: 20px 0;">4개의 개인화 문안이 준비되었습니다.</p>
      <a href="${url}" target="_blank" style="
        display: inline-block;
        padding: 15px 30px;
        background: #4f46e5;
        color: white;
        text-decoration: none;
        border-radius: 8px;
        font-weight: bold;
      ">📝 문안 선택하기</a>
      <p style="margin-top: 20px; font-size: 12px; color: #666;">
        새 창에서 열립니다. 문안 선택 후 자동 발송됩니다.
      </p>
    </div>
    <script>
      window.open('${url}', '_blank', 'width=1200,height=800');
    </script>
  `;
  
  const htmlOutput = HtmlService.createHtmlOutput(html).setWidth(500).setHeight(300);
  SpreadsheetApp.getUi().showModalDialog(htmlOutput, `${companyName} - AI 메일 선택`);
}

/**
 * 서버 가이드 표시
 */
function showServerGuide() {
  SpreadsheetApp.getUi().alert(
    '서버 시작 가이드',
    '터미널에서 다음 명령어를 실행하세요:\n\ncd /Users/milo/Desktop/ocean/email-copywriting-chatbot\npython3 app.py\n\n서버 시작 후 다시 테스트메일 버튼을 눌러주세요.',
    SpreadsheetApp.getUi().ButtonSet.OK
  );
}
