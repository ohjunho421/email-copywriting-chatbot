/**
 * Google Apps Script - 이메일 챗봇 연동 코드
 * F열 기반 분기 처리 로직
 */

// 설정
const CHATBOT_API_URL = 'http://localhost:5001/api/apps-script-integration';
const CLAUDE_EMAIL_TYPE = 'claude 개인화 메일';

/**
 * 1차 메일 발송 (수정된 버전 - F열 분기 처리)
 */
function batchSendFirstEmailWithChatbot(useUI = true) {
  try {
    const sheet = SpreadsheetApp.getActiveSheet();
    const data = sheet.getDataRange().getValues();
    const headers = data[0];
    
    // F열 인덱스 찾기 (이메일템플릿형식)
    const emailTemplateColumnIndex = headers.indexOf('이메일템플릿형식');
    if (emailTemplateColumnIndex === -1) {
      throw new Error('이메일템플릿형식 열을 찾을 수 없습니다.');
    }
    
    let claudeEmailCount = 0;
    let traditionalEmailCount = 0;
    
    // 각 행 처리
    for (let i = 1; i < data.length; i++) {
      const row = data[i];
      const emailTemplateType = row[emailTemplateColumnIndex];
      
      // 회사명이 없으면 스킵
      if (!row[0]) continue;
      
      // 이미 발송된 메일은 스킵
      if (row[headers.indexOf('1차발송여부')]) continue;
      
      if (emailTemplateType === CLAUDE_EMAIL_TYPE) {
        // Claude 개인화 메일 처리
        handleClaudePersonalizedEmail(row, headers, i + 1, sheet);
        claudeEmailCount++;
      } else {
        // 기존 템플릿 메일 처리
        handleTraditionalEmail(row, headers, i + 1, sheet);
        traditionalEmailCount++;
      }
    }
    
    if (useUI) {
      const message = `발송 완료!\n- Claude 개인화 메일: ${claudeEmailCount}건\n- 기존 템플릿 메일: ${traditionalEmailCount}건`;
      SpreadsheetApp.getUi().alert('발송 결과', message, SpreadsheetApp.getUi().ButtonSet.OK);
    }
    
    console.log(`1차 메일 발송 완료 - Claude: ${claudeEmailCount}, 기존: ${traditionalEmailCount}`);
    
  } catch (error) {
    console.error('1차 메일 발송 오류:', error);
    if (useUI) {
      SpreadsheetApp.getUi().alert('오류', `발송 중 오류가 발생했습니다: ${error.message}`, SpreadsheetApp.getUi().ButtonSet.OK);
    }
  }
}

/**
 * Claude 개인화 메일 처리
 */
function handleClaudePersonalizedEmail(row, headers, rowIndex, sheet) {
  try {
    console.log(`Claude 개인화 메일 처리 시작: 행 ${rowIndex}`);
    
    // 회사 데이터 추출
    const companyData = extractCompanyData(row, headers);
    
    // Python 챗봇 API 호출
    const response = callChatbotAPI(companyData);
    
    if (response.success) {
      // 웹 인터페이스 URL을 사용자에게 제공
      const interfaceUrl = response.interface_url;
      const companyName = companyData['회사명'];
      
      console.log(`${companyName} 웹 인터페이스 생성: ${interfaceUrl}`);
      
      // 사용자에게 웹 인터페이스 링크 제공
      showEmailInterface(companyName, interfaceUrl, rowIndex, sheet);
      
    } else {
      console.error(`Claude 메일 생성 실패: ${response.error}`);
      // 실패 시 기존 템플릿으로 폴백
      handleTraditionalEmail(row, headers, rowIndex, sheet);
    }
    
  } catch (error) {
    console.error(`Claude 개인화 메일 처리 오류 (행 ${rowIndex}):`, error);
    // 오류 시 기존 템플릿으로 폴백
    handleTraditionalEmail(row, headers, rowIndex, sheet);
  }
}

/**
 * 기존 템플릿 메일 처리
 */
function handleTraditionalEmail(row, headers, rowIndex, sheet) {
  try {
    console.log(`기존 템플릿 메일 처리: 행 ${rowIndex}`);
    
    // 기존 firstEmailTemplate 로직 호출
    // 여기서는 기존 Apps Script의 sendFirstEmail 함수를 호출
    const emailContent = getFirstEmailContents(row, headers);
    const success = sendEmailWithTemplate(emailContent, row, headers);
    
    if (success) {
      // 발송 성공 시 시트 업데이트
      updateSentStatus(sheet, rowIndex, '1차발송여부');
      console.log(`기존 템플릿 메일 발송 완료: 행 ${rowIndex}`);
    }
    
  } catch (error) {
    console.error(`기존 템플릿 메일 처리 오류 (행 ${rowIndex}):`, error);
  }
}

/**
 * 회사 데이터 추출
 */
function extractCompanyData(row, headers) {
  const companyData = {};
  
  // 헤더와 데이터 매핑
  for (let i = 0; i < headers.length; i++) {
    if (row[i]) {
      companyData[headers[i]] = row[i];
    }
  }
  
  return companyData;
}

/**
 * Python 챗봇 API 호출
 */
function callChatbotAPI(companyData) {
  try {
    const payload = {
      company_data: companyData
    };
    
    const options = {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      payload: JSON.stringify(payload)
    };
    
    const response = UrlFetchApp.fetch(CHATBOT_API_URL, options);
    const responseData = JSON.parse(response.getContentText());
    
    return responseData;
    
  } catch (error) {
    console.error('챗봇 API 호출 오류:', error);
    return { success: false, error: error.message };
  }
}

/**
 * 웹 인터페이스 표시
 */
function showEmailInterface(companyName, interfaceUrl, rowIndex, sheet) {
  try {
    // HTML 다이얼로그로 웹 인터페이스 링크 제공
    const htmlContent = `
      <div style="padding: 20px; font-family: Arial, sans-serif;">
        <h2>🚀 ${companyName} 개인화 이메일 생성 완료</h2>
        <p>4개의 맞춤 문안이 생성되었습니다.</p>
        <p>아래 링크를 클릭하여 문안을 선택하고 편집하세요:</p>
        <p style="margin: 20px 0;">
          <a href="${interfaceUrl}" target="_blank" style="
            display: inline-block;
            padding: 12px 24px;
            background: #4f46e5;
            color: white;
            text-decoration: none;
            border-radius: 8px;
            font-weight: bold;
          ">📝 이메일 문안 선택하기</a>
        </p>
        <p style="font-size: 12px; color: #666;">
          * 새 창에서 열립니다. 문안 선택 후 자동으로 발송됩니다.
        </p>
        <script>
          // 자동으로 새 창에서 열기
          window.open('${interfaceUrl}', '_blank', 'width=1200,height=800');
        </script>
      </div>
    `;
    
    const htmlOutput = HtmlService.createHtmlOutput(htmlContent)
      .setWidth(500)
      .setHeight(300);
    
    SpreadsheetApp.getUi().showModalDialog(htmlOutput, `${companyName} 이메일 문안 선택`);
    
    // 임시로 처리 중 상태 표시
    const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
    const statusColumnIndex = headers.indexOf('1차발송여부') + 1;
    if (statusColumnIndex > 0) {
      sheet.getRange(rowIndex, statusColumnIndex).setValue('처리 중...');
    }
    
  } catch (error) {
    console.error('웹 인터페이스 표시 오류:', error);
  }
}

/**
 * 발송 상태 업데이트
 */
function updateSentStatus(sheet, rowIndex, statusColumn) {
  try {
    const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
    const columnIndex = headers.indexOf(statusColumn) + 1;
    
    if (columnIndex > 0) {
      const now = new Date();
      const dateString = Utilities.formatDate(now, Session.getScriptTimeZone(), 'yyyy-MM-dd HH:mm:ss');
      sheet.getRange(rowIndex, columnIndex).setValue(dateString);
    }
    
  } catch (error) {
    console.error('발송 상태 업데이트 오류:', error);
  }
}

/**
 * 챗봇에서 최종 이메일 수신 시 호출되는 콜백 함수
 */
function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);
    const sessionId = data.session_id;
    const finalEmail = data.final_email;
    const companyData = data.company_data;
    
    console.log(`최종 이메일 수신: ${companyData['회사명']}`);
    
    // 실제 이메일 발송
    const success = sendFinalEmail(finalEmail, companyData);
    
    if (success) {
      // 시트 업데이트
      updateSheetAfterSending(companyData, finalEmail);
      
      return ContentService
        .createTextOutput(JSON.stringify({ success: true, message: '발송 완료' }))
        .setMimeType(ContentService.MimeType.JSON);
    } else {
      return ContentService
        .createTextOutput(JSON.stringify({ success: false, error: '발송 실패' }))
        .setMimeType(ContentService.MimeType.JSON);
    }
    
  } catch (error) {
    console.error('콜백 처리 오류:', error);
    return ContentService
      .createTextOutput(JSON.stringify({ success: false, error: error.message }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

/**
 * 최종 이메일 발송
 */
function sendFinalEmail(emailData, companyData) {
  try {
    const to = companyData['대표이메일'] || companyData['이메일'];
    const subject = emailData.subject;
    const htmlBody = emailData.body;
    
    // 이메일 발송
    GmailApp.sendEmail(to, subject, '', {
      htmlBody: htmlBody,
      name: 'PortOne 오준호'
    });
    
    console.log(`최종 이메일 발송 완료: ${companyData['회사명']} (${to})`);
    return true;
    
  } catch (error) {
    console.error('최종 이메일 발송 오류:', error);
    return false;
  }
}

/**
 * 발송 후 시트 업데이트
 */
function updateSheetAfterSending(companyData, emailData) {
  try {
    const sheet = SpreadsheetApp.getActiveSheet();
    const data = sheet.getDataRange().getValues();
    const headers = data[0];
    
    // 회사명으로 해당 행 찾기
    const companyName = companyData['회사명'];
    let targetRowIndex = -1;
    
    for (let i = 1; i < data.length; i++) {
      if (data[i][0] === companyName) {
        targetRowIndex = i + 1;
        break;
      }
    }
    
    if (targetRowIndex > 0) {
      // 발송 상태 업데이트
      updateSentStatus(sheet, targetRowIndex, '1차발송여부');
      
      // 이메일 내용 저장 (선택적)
      const emailContentColumnIndex = headers.indexOf('발송이메일내용') + 1;
      if (emailContentColumnIndex > 0) {
        sheet.getRange(targetRowIndex, emailContentColumnIndex).setValue(emailData.body);
      }
      
      console.log(`시트 업데이트 완료: ${companyName} (행 ${targetRowIndex})`);
    }
    
  } catch (error) {
    console.error('시트 업데이트 오류:', error);
  }
}

/**
 * 기존 템플릿 이메일 내용 생성 (기존 함수 호출)
 */
function getFirstEmailContents(row, headers) {
  // 기존 Apps Script의 getFirstEmailContents 함수 호출
  // 이 부분은 기존 코드에 맞게 수정 필요
  return {
    subject: `[PortOne] ${row[0]} ${row[headers.indexOf('담당자명')] || '담당자님'}께 전달 부탁드립니다`,
    body: '기존 템플릿 내용...' // 실제로는 기존 템플릿 로직 사용
  };
}

/**
 * 템플릿 이메일 발송
 */
function sendEmailWithTemplate(emailContent, row, headers) {
  try {
    const to = row[headers.indexOf('대표이메일')] || row[headers.indexOf('이메일')];
    
    GmailApp.sendEmail(to, emailContent.subject, '', {
      htmlBody: emailContent.body,
      name: 'PortOne 오준호'
    });
    
    return true;
  } catch (error) {
    console.error('템플릿 이메일 발송 오류:', error);
    return false;
  }
}

/**
 * 테스트 메일 발송 (수정된 버전 - F열 분기 처리)
 */
function sendTestEmailWithChatbot() {
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
    
    // F열 인덱스 찾기
    const emailTemplateColumnIndex = headers.indexOf('이메일템플릿형식');
    if (emailTemplateColumnIndex === -1) {
      throw new Error('이메일템플릿형식 열을 찾을 수 없습니다.');
    }
    
    const emailTemplateType = row[emailTemplateColumnIndex];
    const companyName = row[0];
    
    console.log(`테스트 메일 발송 시작: ${companyName} (행 ${selectedRow})`);
    
    if (emailTemplateType === CLAUDE_EMAIL_TYPE) {
      // Claude 개인화 메일 처리
      handleClaudePersonalizedEmail(row, headers, selectedRow, sheet, true); // 테스트 모드
      SpreadsheetApp.getUi().alert('테스트 메일', `${companyName}에 대한 개인화 메일 문안이 생성되었습니다.\n웹 인터페이스에서 확인해주세요.`, SpreadsheetApp.getUi().ButtonSet.OK);
    } else {
      // 기존 템플릿 메일 처리
      const emailContent = getFirstEmailContents(row, headers);
      const success = sendEmailWithTemplate(emailContent, row, headers);
      
      if (success) {
        SpreadsheetApp.getUi().alert('테스트 메일', `${companyName}에게 테스트 메일이 발송되었습니다.`, SpreadsheetApp.getUi().ButtonSet.OK);
        console.log(`테스트 메일 발송 완료: ${companyName}`);
      } else {
        SpreadsheetApp.getUi().alert('오류', `${companyName} 테스트 메일 발송에 실패했습니다.`, SpreadsheetApp.getUi().ButtonSet.OK);
      }
    }
    
  } catch (error) {
    console.error('테스트 메일 발송 오류:', error);
    SpreadsheetApp.getUi().alert('오류', `테스트 메일 발송 중 오류가 발생했습니다: ${error.message}`, SpreadsheetApp.getUi().ButtonSet.OK);
  }
}

/**
 * 메뉴에 추가할 함수들
 */
function onOpen() {
  const ui = SpreadsheetApp.getUi();
  ui.createMenu('📧 PortOne 이메일')
    .addItem('🚀 1차메일 발송 (AI 개인화 포함)', 'batchSendFirstEmailWithChatbot')
    .addItem('🧪 테스트메일 발송 (AI 개인화 포함)', 'sendTestEmailWithChatbot')
    .addItem('📊 발송 현황 확인', 'checkSendingStatus')
    .addToUi();
}

/**
 * 발송 현황 확인
 */
function checkSendingStatus() {
  try {
    const sheet = SpreadsheetApp.getActiveSheet();
    const data = sheet.getDataRange().getValues();
    const headers = data[0];
    
    let totalCount = 0;
    let sentCount = 0;
    let claudeCount = 0;
    let traditionalCount = 0;
    
    const emailTemplateColumnIndex = headers.indexOf('이메일템플릿형식');
    const sentColumnIndex = headers.indexOf('1차발송여부');
    
    for (let i = 1; i < data.length; i++) {
      const row = data[i];
      if (!row[0]) continue; // 회사명이 없으면 스킵
      
      totalCount++;
      
      if (row[sentColumnIndex]) {
        sentCount++;
      }
      
      if (row[emailTemplateColumnIndex] === CLAUDE_EMAIL_TYPE) {
        claudeCount++;
      } else {
        traditionalCount++;
      }
    }
    
    const message = `📊 발송 현황\n\n` +
                   `전체 대상: ${totalCount}건\n` +
                   `발송 완료: ${sentCount}건\n` +
                   `발송 대기: ${totalCount - sentCount}건\n\n` +
                   `📝 문안 유형별:\n` +
                   `- Claude 개인화: ${claudeCount}건\n` +
                   `- 기존 템플릿: ${traditionalCount}건`;
    
    SpreadsheetApp.getUi().alert('발송 현황', message, SpreadsheetApp.getUi().ButtonSet.OK);
    
  } catch (error) {
    console.error('발송 현황 확인 오류:', error);
    SpreadsheetApp.getUi().alert('오류', `현황 확인 중 오류가 발생했습니다: ${error.message}`, SpreadsheetApp.getUi().ButtonSet.OK);
  }
}
