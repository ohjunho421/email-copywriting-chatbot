/**
 * 기존 테스트메일 함수를 보존하면서 새로운 스마트 테스트메일 함수 추가
 * 
 * 사용법:
 * 1. 기존 sendTestEmail 함수는 그대로 두기
 * 2. 아래 코드를 추가하여 새로운 sendSmartTestEmail 함수 생성
 * 3. 메뉴에서 새 함수 사용
 */

/**
 * 스마트 테스트메일 함수 (Claude 개인화 메일 자동 감지)
 */
function sendSmartTestEmail() {
  try {
    console.log('🧪 스마트 테스트메일 시작');
    
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
    
    console.log(`스마트 테스트메일: ${companyName}, 템플릿: "${emailTemplateType}"`);
    
    // Claude 개인화 메일 여부 확인
    if (emailTemplateType === 'claude 개인화 메일') {
      console.log('🤖 Claude 개인화 메일 감지');
      handleSmartClaudeTest(row, headers, selectedRow, sheet);
    } else {
      console.log('📧 기존 템플릿 메일 - 기존 함수 호출');
      
      // 기존 테스트메일 함수 호출
      if (typeof sendTestEmail === 'function') {
        sendTestEmail();
      } else {
        SpreadsheetApp.getUi().alert('오류', '기존 테스트메일 함수를 찾을 수 없습니다.', SpreadsheetApp.getUi().ButtonSet.OK);
      }
    }
    
  } catch (error) {
    console.error('스마트 테스트메일 오류:', error);
    SpreadsheetApp.getUi().alert('오류', `스마트 테스트메일 오류: ${error.message}`, SpreadsheetApp.getUi().ButtonSet.OK);
  }
}

/**
 * Claude 개인화 테스트메일 처리 (스마트 버전)
 */
function handleSmartClaudeTest(row, headers, rowIndex, sheet) {
  try {
    console.log('🚀 Claude 개인화 테스트메일 처리');
    
    // 1. 서버 상태 확인 및 자동 시작
    const serverReady = ensureServerReady();
    
    if (!serverReady) {
      console.log('❌ 서버 준비 실패');
      return;
    }
    
    // 2. 챗봇 API 호출
    console.log('✅ 서버 준비 완료 - API 호출');
    
    const companyData = {};
    for (let i = 0; i < headers.length; i++) {
      if (row[i]) {
        companyData[headers[i]] = row[i];
      }
    }
    
    const response = callSmartChatbotAPI(companyData);
    
    if (response.success) {
      const companyName = companyData['회사명'] || 'Unknown';
      
      console.log(`✅ 웹 인터페이스 생성: ${response.interface_url}`);
      
      // 테스트메일용 웹 인터페이스 표시
      showSmartTestInterface(companyName, response.interface_url);
      
    } else {
      console.error(`❌ API 호출 실패: ${response.error}`);
      SpreadsheetApp.getUi().alert('오류', `AI 메일 생성 실패:\n${response.error}`, SpreadsheetApp.getUi().ButtonSet.OK);
    }
    
  } catch (error) {
    console.error('Claude 테스트메일 처리 오류:', error);
    SpreadsheetApp.getUi().alert('오류', `처리 중 오류: ${error.message}`, SpreadsheetApp.getUi().ButtonSet.OK);
  }
}

/**
 * 서버 준비 보장 (자동 시작 포함)
 */
function ensureServerReady() {
  try {
    // 1. 현재 서버 상태 확인
    if (isSmartServerRunning()) {
      console.log('✅ 서버가 이미 실행 중');
      return true;
    }
    
    console.log('⚠️ 서버가 실행되지 않음 - 자동 시작 시도');
    
    // 2. 사용자에게 자동 시작 확인
    const ui = SpreadsheetApp.getUi();
    const response = ui.alert(
      '🤖 AI 서버 시작 필요',
      'Claude 개인화 메일을 위해 Python 서버를 시작해야 합니다.\n\n자동으로 시작하시겠습니까?',
      ui.ButtonSet.YES_NO_CANCEL
    );
    
    if (response === ui.Button.YES) {
      // 3. 자동 시작 시도
      const startSuccess = attemptSmartServerStart();
      
      if (startSuccess) {
        // 4. 사용자에게 대기 안내
        ui.alert(
          '서버 시작 중',
          '🚀 Python 서버를 시작했습니다.\n\n약 15초 후에 다시 테스트메일 버튼을 눌러주세요.\n\n터미널 창이 열리면 서버가 시작되고 있는 것입니다.',
          ui.ButtonSet.OK
        );
        return false; // 사용자가 다시 시도하도록
      } else {
        // 5. 자동 시작 실패 시 수동 가이드
        showSmartManualGuide();
        return false;
      }
    } else if (response === ui.Button.NO) {
      // 수동 시작 가이드
      showSmartManualGuide();
      return false;
    } else {
      // 취소
      return false;
    }
    
  } catch (error) {
    console.error('서버 준비 오류:', error);
    return false;
  }
}

/**
 * 서버 실행 상태 확인
 */
function isSmartServerRunning() {
  try {
    const response = UrlFetchApp.fetch('http://localhost:5001/api/health', {
      method: 'GET',
      muteHttpExceptions: true
    });
    
    const isRunning = response.getResponseCode() === 200;
    console.log(`서버 상태 확인: ${isRunning ? '실행 중' : '중지됨'}`);
    return isRunning;
    
  } catch (error) {
    console.log('서버 상태 확인 실패:', error.message);
    return false;
  }
}

/**
 * 서버 자동 시작 시도
 */
function attemptSmartServerStart() {
  try {
    console.log('🚀 서버 자동 시작 시도');
    
    // AppleScript로 터미널에서 서버 시작
    const script = `
      tell application "Terminal"
        activate
        do script "cd /Users/milo/Desktop/ocean/email-copywriting-chatbot && echo '🚀 PortOne AI 챗봇 서버 시작 중...' && python3 app.py"
      end tell
    `;
    
    // AppleScript 실행
    Utilities.exec('osascript', ['-e', script]);
    
    console.log('✅ 서버 시작 명령 실행됨');
    return true;
    
  } catch (error) {
    console.error('❌ 서버 자동 시작 실패:', error);
    return false;
  }
}

/**
 * 챗봇 API 호출 (스마트 버전)
 */
function callSmartChatbotAPI(companyData) {
  try {
    console.log('📡 스마트 챗봇 API 호출');
    
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
    
    console.log(`API 응답: ${responseCode}`);
    
    if (responseCode !== 200) {
      return { 
        success: false, 
        error: `서버 오류 (${responseCode}): ${responseText}` 
      };
    }
    
    const responseData = JSON.parse(responseText);
    return responseData;
    
  } catch (error) {
    console.error('API 호출 오류:', error);
    return { 
      success: false, 
      error: `연결 실패: ${error.message}\n\n서버가 실행 중인지 확인해주세요.` 
    };
  }
}

/**
 * 스마트 테스트 인터페이스 표시
 */
function showSmartTestInterface(companyName, interfaceUrl) {
  const htmlContent = `
    <div style="padding: 30px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; text-align: center; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 16px;">
      
      <div style="background: rgba(255,255,255,0.1); padding: 25px; border-radius: 12px; margin-bottom: 25px;">
        <h2 style="margin: 0 0 15px 0; font-size: 24px;">🧪 ${companyName}</h2>
        <h3 style="margin: 0; font-size: 18px; font-weight: normal; opacity: 0.9;">AI 개인화 테스트메일 준비 완료!</h3>
      </div>
      
      <div style="background: rgba(255,255,255,0.95); color: #1f2937; padding: 25px; border-radius: 12px; margin: 20px 0;">
        <div style="display: flex; align-items: center; justify-content: center; margin-bottom: 20px;">
          <div style="width: 40px; height: 40px; background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%); border-radius: 50%; display: flex; align-items: center; justify-content: center; margin-right: 15px;">
            <span style="font-size: 20px;">🤖</span>
          </div>
          <div style="text-align: left;">
            <h4 style="margin: 0; color: #1f2937;">4개의 맞춤 문안 생성 완료</h4>
            <p style="margin: 5px 0 0 0; color: #6b7280; font-size: 14px;">OPI & 재무자동화 × 전문적 & 호기심 유발형</p>
          </div>
        </div>
        
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
          transition: all 0.3s ease;
          margin: 10px;
        " onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 6px 20px rgba(79, 70, 229, 0.4)'" 
           onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 4px 15px rgba(79, 70, 229, 0.3)'">
          📝 테스트메일 문안 선택하기
        </a>
      </div>
      
      <div style="background: rgba(255,255,255,0.1); padding: 20px; border-radius: 8px; margin: 20px 0;">
        <h4 style="margin: 0 0 10px 0; font-size: 16px;">💡 테스트 모드 안내</h4>
        <div style="font-size: 14px; opacity: 0.9; line-height: 1.5;">
          ✅ 새 창에서 문안 선택 인터페이스가 열립니다<br>
          ✅ 4개 문안 중 선택하고 실시간 편집 가능<br>
          ✅ AI로 문안 개선 요청 가능<br>
          ✅ 최종 선택 후 테스트 발송됩니다
        </div>
      </div>
      
      <div style="margin-top: 25px;">
        <button onclick="google.script.host.close()" style="
          padding: 12px 24px;
          background: rgba(255,255,255,0.2);
          color: white;
          border: 1px solid rgba(255,255,255,0.3);
          border-radius: 8px;
          cursor: pointer;
          font-size: 14px;
          transition: all 0.3s ease;
        " onmouseover="this.style.background='rgba(255,255,255,0.3)'" 
           onmouseout="this.style.background='rgba(255,255,255,0.2)'">
          닫기
        </button>
      </div>
    </div>
    
    <script>
      // 자동으로 새 창에서 열기
      setTimeout(() => {
        window.open('${interfaceUrl}', '_blank', 'width=1200,height=800,scrollbars=yes,resizable=yes');
      }, 500);
    </script>
  `;
  
  const htmlOutput = HtmlService.createHtmlOutput(htmlContent)
    .setWidth(650)
    .setHeight(500);
  
  SpreadsheetApp.getUi().showModalDialog(htmlOutput, `${companyName} - AI 테스트메일`);
}

/**
 * 수동 서버 가이드 (스마트 버전)
 */
function showSmartManualGuide() {
  const htmlContent = `
    <div style="padding: 25px; font-family: Arial, sans-serif; line-height: 1.6;">
      <h2 style="color: #dc2626; margin-bottom: 20px;">🛠️ Python 서버 수동 시작</h2>
      
      <div style="background: #fee2e2; padding: 15px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #dc2626;">
        <p style="margin: 0; color: #991b1b;">
          <strong>자동 시작에 실패했습니다.</strong><br>
          터미널에서 수동으로 서버를 시작해주세요.
        </p>
      </div>
      
      <h3 style="color: #374151; margin-bottom: 15px;">📋 단계별 가이드:</h3>
      
      <div style="background: #f3f4f6; padding: 20px; border-radius: 8px; margin: 15px 0;">
        <h4 style="margin-top: 0; color: #1f2937;">1️⃣ 터미널 열기</h4>
        <p style="margin: 5px 0; color: #4b5563;">Applications > Utilities > Terminal</p>
        
        <h4 style="margin: 15px 0 5px 0; color: #1f2937;">2️⃣ 명령어 실행</h4>
        <div style="background: #1f2937; color: #10b981; padding: 12px; border-radius: 6px; font-family: monospace; font-size: 13px; margin: 10px 0;">
cd /Users/milo/Desktop/ocean/email-copywriting-chatbot<br>
python3 app.py
        </div>
        
        <h4 style="margin: 15px 0 5px 0; color: #1f2937;">3️⃣ 서버 시작 확인</h4>
        <p style="margin: 5px 0; color: #4b5563;">터미널에 "Running on http://localhost:5001" 메시지가 나타나면 성공</p>
        
        <h4 style="margin: 15px 0 5px 0; color: #1f2937;">4️⃣ 다시 테스트</h4>
        <p style="margin: 5px 0; color: #4b5563;">서버 시작 후 다시 "스마트 테스트메일" 버튼 클릭</p>
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
    .setWidth(600)
    .setHeight(500);
  
  SpreadsheetApp.getUi().showModalDialog(htmlOutput, 'Python 서버 시작 가이드');
}

/**
 * 업데이트된 메뉴 (기존 함수 보존)
 */
function onOpen() {
  const ui = SpreadsheetApp.getUi();
  
  // 기존 메뉴는 그대로 두고 새로운 메뉴 추가
  ui.createMenu('🚀 PortOne AI 메일')
    .addItem('📧 1차메일 발송 (스마트)', 'sendSmartBatchEmail')
    .addItem('🧪 테스트메일 (스마트)', 'sendSmartTestEmail')
    .addSeparator()
    .addItem('🔍 서버 상태 확인', 'checkSmartServerStatus')
    .addItem('📖 서버 시작 가이드', 'showSmartManualGuide')
    .addToUi();
}

/**
 * 서버 상태 확인 (스마트 버전)
 */
function checkSmartServerStatus() {
  if (isSmartServerRunning()) {
    SpreadsheetApp.getUi().alert(
      '서버 상태', 
      '✅ Python AI 챗봇 서버가 정상 작동 중입니다!\n\n🌐 주소: http://localhost:5001\n🤖 상태: Claude 개인화 메일 준비 완료\n\n이제 스마트 테스트메일을 사용할 수 있습니다.', 
      SpreadsheetApp.getUi().ButtonSet.OK
    );
  } else {
    SpreadsheetApp.getUi().alert(
      '서버 상태', 
      '❌ Python AI 챗봇 서버가 실행되지 않았습니다.\n\n💡 해결 방법:\n1. "🧪 테스트메일 (스마트)" 버튼 클릭\n2. 자동 시작 선택\n3. 또는 수동으로 터미널에서 시작\n\n📝 기존 템플릿 메일은 서버 없이도 사용 가능합니다.', 
      SpreadsheetApp.getUi().ButtonSet.OK
    );
  }
}
