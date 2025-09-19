/**
 * 기존 Apps Script 프로젝트의 테스트메일 함수를 완전히 대체하는 코드
 * 
 * 사용법:
 * 1. 기존 sendTestEmail 함수를 찾아서 이름을 sendTestEmailOriginal로 변경
 * 2. 아래 코드를 추가하여 새로운 sendTestEmail 함수로 사용
 */

/**
 * 새로운 테스트메일 함수 (Claude 개인화 메일 지원)
 * 기존 sendTestEmail 함수를 완전히 대체
 */
function sendTestEmail() {
  try {
    console.log('🧪 새로운 테스트메일 함수 시작');
    
    const sheet = SpreadsheetApp.getActiveSheet();
    const selection = sheet.getActiveRange();
    const selectedRow = selection.getRow();
    
    // 선택된 행 확인
    if (selectedRow <= 1) {
      SpreadsheetApp.getUi().alert('오류', '테스트할 행을 선택해주세요.', SpreadsheetApp.getUi().ButtonSet.OK);
      return;
    }
    
    const data = sheet.getDataRange().getValues();
    const headers = data[0];
    const row = data[selectedRow - 1];
    
    // 회사명 확인
    const companyName = row[0];
    if (!companyName) {
      SpreadsheetApp.getUi().alert('오류', '회사명이 없는 행입니다.', SpreadsheetApp.getUi().ButtonSet.OK);
      return;
    }
    
    // F열(이메일템플릿형식) 확인
    const emailTemplateColumnIndex = headers.indexOf('이메일템플릿형식');
    let emailTemplateType = '';
    
    if (emailTemplateColumnIndex !== -1) {
      emailTemplateType = row[emailTemplateColumnIndex] || '';
    }
    
    console.log(`테스트메일: ${companyName}, 템플릿: ${emailTemplateType}`);
    
    // Claude 개인화 메일인지 확인
    if (emailTemplateType === 'claude 개인화 메일') {
      console.log('🤖 Claude 개인화 메일 감지 - 챗봇 서비스 시작');
      handleClaudeTestEmail(row, headers, selectedRow, sheet);
    } else {
      console.log('📧 기존 템플릿 메일 - 기존 방식 사용');
      handleTraditionalTestEmail(row, headers, selectedRow, sheet);
    }
    
  } catch (error) {
    console.error('테스트메일 오류:', error);
    SpreadsheetApp.getUi().alert('오류', `테스트메일 발송 중 오류: ${error.message}`, SpreadsheetApp.getUi().ButtonSet.OK);
  }
}

/**
 * Claude 개인화 테스트메일 처리
 */
function handleClaudeTestEmail(row, headers, rowIndex, sheet) {
  try {
    console.log('🚀 Claude 개인화 테스트메일 처리 시작');
    
    // 1. 서버 상태 확인
    const serverRunning = checkServerStatus();
    
    if (!serverRunning) {
      // 서버가 실행되지 않았으면 시작 안내
      const startServer = showServerStartDialog();
      
      if (startServer) {
        // 자동 서버 시작 시도
        attemptServerStart();
        
        // 사용자에게 재시도 안내
        SpreadsheetApp.getUi().alert(
          '서버 시작 중',
          '🚀 Python 서버를 시작했습니다.\n\n15초 정도 기다린 후 다시 테스트메일 버튼을 눌러주세요.',
          SpreadsheetApp.getUi().ButtonSet.OK
        );
        return;
      } else {
        // 수동 시작 가이드
        showManualServerGuide();
        return;
      }
    }
    
    // 2. 서버가 실행 중이면 챗봇 API 호출
    console.log('✅ 서버 실행 중 - 챗봇 API 호출');
    
    // 회사 데이터 추출
    const companyData = extractCompanyDataFromRow(row, headers);
    
    // Python 챗봇 API 호출
    const response = callChatbotAPI(companyData);
    
    if (response.success) {
      const interfaceUrl = response.interface_url;
      const companyName = companyData['회사명'] || 'Unknown';
      
      console.log(`✅ 웹 인터페이스 생성 성공: ${interfaceUrl}`);
      
      // 웹 인터페이스 표시
      showEmailInterfaceForTest(companyName, interfaceUrl);
      
    } else {
      console.error(`❌ Claude 메일 생성 실패: ${response.error}`);
      SpreadsheetApp.getUi().alert('오류', `AI 메일 생성 실패: ${response.error}`, SpreadsheetApp.getUi().ButtonSet.OK);
    }
    
  } catch (error) {
    console.error('Claude 테스트메일 처리 오류:', error);
    SpreadsheetApp.getUi().alert('오류', `처리 중 오류: ${error.message}`, SpreadsheetApp.getUi().ButtonSet.OK);
  }
}

/**
 * 기존 템플릿 테스트메일 처리
 */
function handleTraditionalTestEmail(row, headers, rowIndex, sheet) {
  try {
    console.log('📧 기존 템플릿 테스트메일 처리');
    
    // 기존 로직 호출 (원래 sendTestEmail 함수의 내용)
    // 여기서는 기존 함수를 sendTestEmailOriginal로 이름 변경했다고 가정
    if (typeof sendTestEmailOriginal === 'function') {
      sendTestEmailOriginal();
    } else {
      // 기존 함수가 없으면 간단한 테스트메일 발송
      sendSimpleTestEmail(row, headers);
    }
    
  } catch (error) {
    console.error('기존 템플릿 테스트메일 오류:', error);
    SpreadsheetApp.getUi().alert('오류', `기존 템플릿 테스트메일 오류: ${error.message}`, SpreadsheetApp.getUi().ButtonSet.OK);
  }
}

/**
 * 서버 상태 확인
 */
function checkServerStatus() {
  try {
    const response = UrlFetchApp.fetch('http://localhost:5001/api/health', {
      method: 'GET',
      muteHttpExceptions: true
    });
    
    return response.getResponseCode() === 200;
  } catch (error) {
    console.log('서버 상태 확인 실패:', error.message);
    return false;
  }
}

/**
 * 서버 시작 다이얼로그
 */
function showServerStartDialog() {
  const ui = SpreadsheetApp.getUi();
  
  const response = ui.alert(
    '🤖 AI 챗봇 서버 필요',
    'Claude 개인화 메일을 위해 Python 서버가 필요합니다.\n\n자동으로 서버를 시작하시겠습니까?',
    ui.ButtonSet.YES_NO
  );
  
  return response === ui.Button.YES;
}

/**
 * 서버 자동 시작 시도
 */
function attemptServerStart() {
  try {
    console.log('🚀 서버 자동 시작 시도');
    
    // AppleScript로 터미널에서 서버 시작
    const script = `
      tell application "Terminal"
        activate
        do script "cd /Users/milo/Desktop/ocean/email-copywriting-chatbot && python3 app.py"
      end tell
    `;
    
    // AppleScript 실행
    const result = Utilities.exec('osascript', ['-e', script]);
    console.log('서버 시작 명령 실행됨');
    
    return true;
    
  } catch (error) {
    console.error('서버 자동 시작 실패:', error);
    return false;
  }
}

/**
 * 회사 데이터 추출
 */
function extractCompanyDataFromRow(row, headers) {
  const companyData = {};
  
  for (let i = 0; i < headers.length; i++) {
    if (row[i]) {
      companyData[headers[i]] = row[i];
    }
  }
  
  return companyData;
}

/**
 * 챗봇 API 호출
 */
function callChatbotAPI(companyData) {
  try {
    console.log('📡 챗봇 API 호출:', 'http://localhost:5001/api/apps-script-integration');
    
    const payload = {
      company_data: companyData
    };
    
    const options = {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    };
    
    const response = UrlFetchApp.fetch('http://localhost:5001/api/apps-script-integration', options);
    const responseCode = response.getResponseCode();
    const responseText = response.getContentText();
    
    console.log(`API 응답 코드: ${responseCode}`);
    
    if (responseCode !== 200) {
      throw new Error(`API 호출 실패 (${responseCode}): ${responseText}`);
    }
    
    const responseData = JSON.parse(responseText);
    return responseData;
    
  } catch (error) {
    console.error('챗봇 API 호출 오류:', error);
    return { 
      success: false, 
      error: `API 연결 실패: ${error.message}` 
    };
  }
}

/**
 * 테스트용 웹 인터페이스 표시
 */
function showEmailInterfaceForTest(companyName, interfaceUrl) {
  const htmlContent = `
    <div style="padding: 25px; font-family: Arial, sans-serif; text-align: center;">
      <h2 style="color: #4f46e5; margin-bottom: 20px;">🧪 ${companyName} 테스트메일 생성 완료</h2>
      
      <div style="background: #f0f9ff; padding: 20px; border-radius: 12px; margin: 20px 0; border-left: 4px solid #0ea5e9;">
        <p style="margin: 0; color: #0c4a6e; font-size: 16px;">
          <strong>4개의 개인화 문안이 생성되었습니다!</strong><br>
          아래 버튼을 클릭하여 문안을 선택하고 편집하세요.
        </p>
      </div>
      
      <div style="margin: 30px 0;">
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
          transition: transform 0.2s;
        " onmouseover="this.style.transform='translateY(-2px)'" onmouseout="this.style.transform='translateY(0)'">
          📝 테스트메일 문안 선택하기
        </a>
      </div>
      
      <div style="background: #fef3c7; padding: 15px; border-radius: 8px; margin: 20px 0;">
        <p style="margin: 0; color: #92400e; font-size: 14px;">
          💡 <strong>테스트 모드:</strong><br>
          • 새 창에서 웹 인터페이스가 열립니다<br>
          • 문안 선택 후 테스트 발송됩니다<br>
          • 실제 고객에게는 발송되지 않습니다
        </p>
      </div>
      
      <div style="text-align: center; margin-top: 25px;">
        <button onclick="google.script.host.close()" style="
          padding: 10px 20px;
          background: #6b7280;
          color: white;
          border: none;
          border-radius: 6px;
          cursor: pointer;
        ">닫기</button>
      </div>
    </div>
    
    <script>
      // 자동으로 새 창에서 열기
      window.open('${interfaceUrl}', '_blank', 'width=1200,height=800,scrollbars=yes,resizable=yes');
    </script>
  `;
  
  const htmlOutput = HtmlService.createHtmlOutput(htmlContent)
    .setWidth(600)
    .setHeight(450);
  
  SpreadsheetApp.getUi().showModalDialog(htmlOutput, `${companyName} - 테스트메일 문안 선택`);
}

/**
 * 수동 서버 가이드 (간단 버전)
 */
function showManualServerGuide() {
  SpreadsheetApp.getUi().alert(
    '서버 수동 시작',
    '🛠️ 터미널에서 다음 명령어를 실행하세요:\n\ncd /Users/milo/Desktop/ocean/email-copywriting-chatbot\npython3 app.py\n\n서버 시작 후 다시 테스트메일 버튼을 눌러주세요.',
    SpreadsheetApp.getUi().ButtonSet.OK
  );
}

/**
 * 간단한 테스트메일 발송 (기존 함수가 없을 때 사용)
 */
function sendSimpleTestEmail(row, headers) {
  try {
    const companyName = row[0];
    const emailAddress = row[headers.indexOf('대표이메일')] || row[headers.indexOf('이메일')];
    
    if (!emailAddress) {
      SpreadsheetApp.getUi().alert('오류', '이메일 주소가 없습니다.', SpreadsheetApp.getUi().ButtonSet.OK);
      return;
    }
    
    const subject = `[PortOne] ${companyName} 담당자님께 전달 부탁드립니다`;
    const body = `안녕하세요, ${companyName} 담당자님.\n\nPortOne 테스트메일입니다.\n\n감사합니다.`;
    
    GmailApp.sendEmail(emailAddress, subject, body);
    
    SpreadsheetApp.getUi().alert('발송 완료', `${companyName}에게 테스트메일이 발송되었습니다.`, SpreadsheetApp.getUi().ButtonSet.OK);
    
  } catch (error) {
    console.error('간단 테스트메일 발송 오류:', error);
    SpreadsheetApp.getUi().alert('오류', `테스트메일 발송 실패: ${error.message}`, SpreadsheetApp.getUi().ButtonSet.OK);
  }
}
