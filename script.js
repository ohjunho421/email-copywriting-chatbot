// 메일 문안 생성 챗봇 JavaScript

// 마크다운 볼드를 HTML로 변환하고 URL을 클릭 가능한 링크로 변환하는 헬퍼 함수
function convertMarkdownToHtml(text) {
    if (!text) return text;
    
    // 1. **텍스트**를 <strong>텍스트</strong>로 변환
    text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    
    // 2. URL을 클릭 가능한 링크로 변환 (http:// 또는 https://로 시작하는 URL)
    // 이미 <a> 태그로 감싸진 URL은 제외
    text = text.replace(/(?<!href=["'])https?:\/\/[^\s<>"]+/g, function(url) {
        // URL 끝에 있는 구두점 제거 (마침표, 쉼표 등)
        let cleanUrl = url.replace(/[.,;!?]+$/, '');
        return `<a href="${cleanUrl}" target="_blank" rel="noopener noreferrer">${cleanUrl}</a>`;
    });
    
    return text;
}

/**
 * HTML을 사용자 친화적 텍스트로 변환
 * - HTML 태그를 보기 쉬운 마크다운 형식으로 변환
 * - 줄바꿈, 볼드체 등을 텍스트로 표현
 */
function convertHtmlToFriendlyText(html) {
    if (!html) return html;
    
    let text = html;
    
    // <br>, <br/>, <br /> → 실제 줄바꿈
    text = text.replace(/<br\s*\/?>/gi, '\n');
    
    // <p>...</p> → 단락 줄바꿈
    text = text.replace(/<\/p>/gi, '\n\n');
    text = text.replace(/<p[^>]*>/gi, '');
    
    // <strong>, <b> → **텍스트** (마크다운 스타일)
    text = text.replace(/<strong>([^<]+)<\/strong>/gi, '**$1**');
    text = text.replace(/<b>([^<]+)<\/b>/gi, '**$1**');
    
    // <em>, <i> → *텍스트* (마크다운 스타일)  
    text = text.replace(/<em>([^<]+)<\/em>/gi, '*$1*');
    text = text.replace(/<i>([^<]+)<\/i>/gi, '*$1*');
    
    // HTML 엔티티 디코딩
    text = text.replace(/&nbsp;/g, ' ');
    text = text.replace(/&quot;/g, '"');
    text = text.replace(/&lt;/g, '<');
    text = text.replace(/&gt;/g, '>');
    text = text.replace(/&amp;/g, '&');
    
    // 나머지 HTML 태그 제거
    text = text.replace(/<[^>]+>/g, '');
    
    // 연속된 줄바꿈 정리 (3개 이상 → 2개)
    text = text.replace(/\n{3,}/g, '\n\n');
    
    // 앞뒤 공백 제거
    text = text.trim();
    
    return text;
}

/**
 * 사용자 친화적 텍스트를 HTML로 변환
 * - **텍스트** → <strong>텍스트</strong>
 * - 줄바꿈 → <br>
 */
function convertFriendlyTextToHtml(text) {
    if (!text) return text;
    
    let html = text;
    
    // 마크다운 볼드 → HTML strong
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    
    // 마크다운 이탤릭 → HTML em (단, ** 안에 있지 않은 경우만)
    html = html.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, '<em>$1</em>');
    
    // 줄바꿈 → <br>
    html = html.replace(/\n/g, '<br>');
    
    return html;
}

class EmailCopywritingChatbot {
    constructor() {
        this.uploadedData = [];
        this.currentCompanyIndex = 0;
        this.isRefinementMode = false;
        this.currentRefinementTarget = null;
        this.userInputMode = 'request'; // 'template' 또는 'request'
        this.sessionData = {  // 세션 데이터 저장
            company_data: null,
            research_data: null,
            current_email: null,
            all_results: []  // 모든 생성 결과
        };
        this.initializeEventListeners();
        this.loadRequestHistory();
        this.portOneValueProps = {
            resourceSaving: {
                title: '85% 리소스 절감',
                description: '개발 및 런칭 리소스를 85% 절감하여 핵심 비즈니스에 집중',
                industries: ['startup', 'sme', 'tech']
            },
            quickSetup: {
                title: '2주 내 구축 완료',
                description: 'PG 컨설팅부터 개발까지 모든 과정을 2주 안에 완료',
                industries: ['all']
            },
            freeConsulting: {
                title: '100만원 상당 무료 컨설팅',
                description: '결제 도메인 전문가의 맞춤형 컨설팅을 무료로 제공',
                industries: ['startup', 'sme']
            },
            smartRouting: {
                title: '스마트 라우팅',
                description: '클릭 한 번으로 결제사 변경 및 트래픽 분산으로 안정성 확보',
                industries: ['enterprise', 'ecommerce']
            },
            unifiedManagement: {
                title: '통합 관리',
                description: '여러 PG사의 결제 내역을 한 페이지에서 통합 관리',
                industries: ['all']
            },
            smartBilling: {
                title: '스마트빌링 솔루션',
                description: '국내 구독결제의 한계를 뛰어넘는 완전한 빌링 시스템을 제공하여 Stripe 대안으로 규제 이슈 없이 안정적인 구독 서비스 운영',
                industries: ['saas']
            },
            gameWebStore: {
                title: '게임 웹상점 구축 서비스',
                description: '인앱결제 수수료(30%)를 피하고 직접 판매가 가능한 게임 전용 웹상점을 PG 추천부터 구축까지 원스톱으로 제공',
                industries: ['gaming']
            },
            subscriptionOptimization: {
                title: '구독 최적화',
                description: '정기결제 실패율 최소화, 던닝 관리, 구독 변경/취소 자동화를 통한 구독 비즈니스 최적화',
                industries: ['saas']
            }
        };
        
        this.industryPainPoints = {
            ecommerce: [
                '결제 실패로 인한 매출 손실',
                '복잡한 PG 연동 과정',
                '결제 데이터 분석의 어려움',
                '정산 관리의 복잡성'
            ],
            fintech: [
                '규제 준수의 복잡성',
                '보안 요구사항 충족',
                '빠른 서비스 출시 압박',
                '개발 리소스 부족'
            ],
            saas: [
                '정기결제 관리의 복잡성',
                '국내 PG의 구독결제 한계',
                'Stripe 사용 시 규제 및 환전 이슈',
                '스마트빌링 시스템 구축 어려움',
                '구독 취소/환불 관리 복잡성',
                '글로벌 결제 지원 및 다화폐 처리'
            ],
            startup: [
                '제한된 개발 리소스',
                '빠른 MVP 출시 필요',
                '비용 효율성',
                '확장성 확보'
            ],
            gaming: [
                '높은 인앱결제 수수료 부담(30%)',
                '웹상점 구축 및 운영의 복잡성',
                'PG사별 게임 특화 서비스 부족',
                '게임 내 결제 전환율 개선',
                '다양한 결제수단 지원 필요',
                '실시간 결제 모니터링 및 관리'
            ],
            default: [
                '결제 시스템 구축의 복잡성',
                '개발 리소스 부족',
                '안정적인 결제 환경 필요'
            ]
        };
    }

    initializeEventListeners() {
        const uploadArea = document.getElementById('uploadArea');
        const fileInput = document.getElementById('fileInput');
        const generateBtn = document.getElementById('generateBtn');
        const clearChatBtn = document.getElementById('clearChat');
        const sendBtn = document.getElementById('sendBtn');
        const userInput = document.getElementById('userInput');

        // 파일 업로드 이벤트
        uploadArea.addEventListener('click', () => fileInput.click());
        uploadArea.addEventListener('dragover', this.handleDragOver.bind(this));
        uploadArea.addEventListener('drop', this.handleDrop.bind(this));
        fileInput.addEventListener('change', this.handleFileSelect.bind(this));

        // 버튼 이벤트
        generateBtn.addEventListener('click', this.generateEmailTemplates.bind(this));
        clearChatBtn.addEventListener('click', this.clearChat.bind(this));
        sendBtn.addEventListener('click', this.sendMessage.bind(this));
        
        // Enter 키 이벤트 (Shift+Enter: 줄바꿈, Enter: 전송)
        // 한국어 IME 조합 중 상태 추적
        let isComposing = false;
        
        userInput.addEventListener('compositionstart', () => {
            isComposing = true;
        });
        
        userInput.addEventListener('compositionend', () => {
            isComposing = false;
        });
        
        userInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey && !isComposing) {
                e.preventDefault(); // 기본 줄바꿈 방지
                this.sendMessage();
            }
        });
    }

    handleDragOver(e) {
        e.preventDefault();
        document.getElementById('uploadArea').classList.add('dragover');
    }

    handleDrop(e) {
        e.preventDefault();
        document.getElementById('uploadArea').classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            this.processFile(files[0]);
        }
    }

    handleFileSelect(e) {
        const file = e.target.files[0];
        if (file) {
            this.processFile(file);
        }
    }

    processFile(file) {
        const fileName = file.name.toLowerCase();
        if (!fileName.endsWith('.csv') && !fileName.endsWith('.txt') && !fileName.endsWith('.tsv')) {
            this.addBotMessage('❌ CSV, TSV, TXT 파일만 업로드 가능합니다.');
            return;
        }

        const reader = new FileReader();
        reader.onload = (e) => {
            try {
                const content = e.target.result;
                // TSV나 TXT 파일이면 탭 구분, CSV면 쉼표 구분
                const isTSV = fileName.endsWith('.txt') || fileName.endsWith('.tsv');
                this.uploadedData = this.parseCSV(content, isTSV);
                this.displayFileInfo(file.name, this.uploadedData.length);
                this.addBotMessage(`✅ ${file.name} 파일이 성공적으로 업로드되었습니다. 총 ${this.uploadedData.length}개 회사 데이터를 확인했습니다.`);
                document.getElementById('generateBtn').disabled = false;
            } catch (error) {
                this.addBotMessage('❌ 파일 처리 중 오류가 발생했습니다: ' + error.message);
            }
        };
        reader.readAsText(file, 'utf-8');
    }

    parseCSV(content, isTSV = false) {
        const lines = content.split('\n').filter(line => line.trim());
        const delimiter = isTSV ? '\t' : ',';
        
        // TSV면 단순 split, CSV면 따옴표 처리
        const headers = isTSV ? lines[0].split(delimiter).map(h => h.trim()) : this.parseCSVLine(lines[0]);
        const data = [];

        console.log(`📋 ${isTSV ? 'TSV' : 'CSV'} 헤더:`, headers);

        for (let i = 1; i < lines.length; i++) {
            const values = isTSV ? lines[i].split(delimiter).map(v => v.trim()) : this.parseCSVLine(lines[i]);
            const row = {};
            headers.forEach((header, index) => {
                row[header] = values[index] || '';
            });
            
            // 디버깅: 첫 번째 데이터 행 출력
            if (i === 1) {
                console.log('📊 첫 번째 행 원본:', lines[i]);
                console.log('📊 파싱된 값들:', values);
                console.log('📊 매핑된 데이터:', row);
            }
            
            // 필수 필드가 있는 행만 포함
            if (row['회사명'] && row['회사명'].trim() !== '') {
                data.push(row);
            }
        }

        return data;
    }

    // CSV 한 줄을 파싱하는 함수 (따옴표 내부의 쉼표는 무시)
    parseCSVLine(line) {
        const result = [];
        let current = '';
        let inQuotes = false;
        
        for (let i = 0; i < line.length; i++) {
            const char = line[i];
            const nextChar = line[i + 1];
            
            if (char === '"') {
                if (inQuotes && nextChar === '"') {
                    // 연속된 따옴표 ("") → 하나의 따옴표로 처리
                    current += '"';
                    i++; // 다음 따옴표 건너뛰기
                } else {
                    // 따옴표 시작 또는 종료
                    inQuotes = !inQuotes;
                }
            } else if (char === ',' && !inQuotes) {
                // 따옴표 밖의 쉼표 → 컬럼 구분자
                result.push(current.trim());
                current = '';
            } else {
                current += char;
            }
        }
        
        // 마지막 컬럼 추가
        result.push(current.trim());
        
        return result;
    }

    displayFileInfo(fileName, rowCount) {
        document.getElementById('fileName').textContent = fileName;
        document.getElementById('rowCount').textContent = rowCount;
        document.getElementById('fileInfo').style.display = 'block';
    }

    async generateEmailTemplates() {
        if (this.uploadedData.length === 0) {
            this.addBotMessage('❌먼저 CSV 파일을 업로드해주세요.');
            return;
        }

        this.showLoading(true);
        this.addBotMessage('🚀 Google Gemini 2.5 Pro로 개인화된 메일 문안을 생성하고 있습니다...');

        try {
            // 모든 회사 처리
            const companiesToProcess = this.uploadedData;
            const totalCompanies = companiesToProcess.length;
            
            // 병렬 처리 설정 (회사 수에 따라 동적 조정)
            let maxWorkers = 3; // 기본값
            if (totalCompanies <= 5) {
                maxWorkers = 2;
            } else if (totalCompanies <= 15) {
                maxWorkers = 3;
            } else if (totalCompanies <= 30) {
                maxWorkers = 5;
            } else {
                maxWorkers = 7;
            }
            
            this.addBotMessage(`📊 총 ${totalCompanies}개 회사를 ${maxWorkers}개 동시 작업으로 병렬 처리를 시작합니다...`);
            this.addBotMessage(`⚡ 예상 시간: 약 ${Math.ceil(totalCompanies / maxWorkers * 15 / 60)}분 (기존 대비 ${Math.round((1 - 1/maxWorkers) * 100)}% 단축)`);
            
            // 진행률 표시를 위한 요소 추가
            this.addProgressIndicator(totalCompanies);
            
            const startTime = Date.now();
            
            // 사용자 입력 가져오기
            const userTemplate = document.getElementById('userTemplate').value.trim();
            
            // 모드에 따른 메시지 표시 및 히스토리 저장
            if (userTemplate) {
                if (this.userInputMode === 'request') {
                    this.addBotMessage('📝 요청사항 모드: AI가 요청사항을 분석하여 맞춤 메일을 생성합니다.');
                    // 요청사항 히스토리에 저장
                    saveRequestToHistory(userTemplate);
                } else {
                    this.addBotMessage('📝 문안 모드: 뉴스 후킹 서론 + 사용자 본문(90%)으로 생성합니다.');
                }
            } else {
                this.addBotMessage('🤖 SSR 모드: 뉴스 후킹 + 4개 문안 생성 + 실제 사례 포함 + 최적의 1개를 AI가 추천합니다.');
            }
            
            // 백엔드 API로 병렬 처리 요청
            const response = await fetch('/api/batch-process', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    companies: companiesToProcess,
                    max_workers: maxWorkers,
                    user_template: userTemplate || null,  // 사용자 입력 전달
                    user_input_mode: this.userInputMode    // 모드 정보 전달
                })
            });

            if (!response.ok) {
                throw new Error(`API 오류: ${response.status}`);
            }

            const result = await response.json();
            
            if (result.success) {
                const processingTime = result.processing_time || ((Date.now() - startTime) / 1000);
                
                this.displayAIGeneratedTemplates(result.results);
                this.addBotMessage(`✅ AI 기반 메일 문안 생성이 완료되었습니다!`);
                this.addBotMessage(`📈 처리 결과: ${result.total_processed}개 회사, ${processingTime}초 소요 (평균 ${(processingTime/totalCompanies).toFixed(1)}초/회사)`);
                this.addBotMessage(`🔥 ${maxWorkers}개 병렬 처리로 ${Math.round((1 - 1/maxWorkers) * 100)}% 시간 단축 효과!`);
                
                // 세션 데이터 저장 (첫 번째 회사 데이터)
                if (result.results && result.results.length > 0) {
                    const firstResult = result.results[0];
                    this.sessionData.company_data = companiesToProcess[0];
                    this.sessionData.research_data = firstResult.research_data || {};
                    this.sessionData.all_results = result.results;
                    
                    // 첫 번째 생성된 이메일 저장
                    if (firstResult.variations) {
                        this.sessionData.current_email = Object.values(firstResult.variations)[0];
                    }
                    
                    console.log('✅ 세션 데이터 저장 완료');
                }
                
                // 메일 생성 완료 후 텍스트박스 활성화
                this.enableUserInput();
            } else {
                throw new Error(result.error || '알 수 없는 오류');
            }
            
        } catch (error) {
            this.addBotMessage('❌ 메일 문안 생성 중 오류가 발생했습니다: ' + error.message);
            this.addBotMessage('💡 백엔드 서버가 실행 중인지 확인해주세요 (python app.py)');
        } finally {
            this.showLoading(false);
            this.removeProgressIndicator();
        }
    }

    async handleChatReply(userMessage) {
        // 새로운 스마트 챗봇 API 사용
        this.showLoading(true);
        this.addBotMessage(`💬 요청을 분석하고 있습니다...`);
        
        try {
            const response = await fetch('/api/smart-chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: userMessage,
                    session_data: this.sessionData  // 세션 데이터 전달
                })
            });
            
            if (!response.ok) {
                throw new Error(`API 오류: ${response.status}`);
            }
            
            const result = await response.json();
            
            if (result.success) {
                // 의도에 따라 다른 표시
                const intent = result.intent;
                
                this.addBotMessage(`✅ ${result.message}`);
                
                if (intent === 'regenerate_with_sales_change') {
                    // 메일 재생성 결과 표시
                    if (result.result && result.result.variations) {
                        this.displayGeneratedEmails(result.result.variations, result.sales_point);
                        // 세션 데이터 업데이트
                        this.sessionData.current_email = Object.values(result.result.variations)[0];
                    }
                } else if (intent === 'change_tone' || intent === 'refine_content') {
                    // 개선된 이메일 표시
                    if (result.result) {
                        this.displayRefinedEmail(result.result);
                        // 세션 데이터 업데이트
                        this.sessionData.current_email = result.result;
                    }
                } else if (intent === 'persuasive_reply') {
                    // 재설득 메일 표시
                    if (result.result && result.result.email) {
                        this.displayChatReply(result.result.email, this.sessionData.company_data?.회사명 || '회사');
                        
                        // 전략 설명
                        if (result.result.email.strategy_used) {
                            this.addBotMessage(`📋 사용된 전략: ${result.result.email.strategy_used}`);
                        }
                        
                        // 핵심 포인트
                        if (result.result.email.key_points && result.result.email.key_points.length > 0) {
                            const points = result.result.email.key_points.map((p, i) => `${i+1}. ${p}`).join('<br>');
                            this.addBotMessage(`🎯 핵심 포인트:<br>${points}`);
                        }
                    }
                } else if (intent === 'question') {
                    // 질문 답변은 이미 message에 포함됨
                    // 추가 처리 없음
                }
            } else {
                // 실패 시에도 message 표시
                this.addBotMessage(`❌ ${result.message || result.error}`);
                
                // 의도 분류 결과 표시 (디버깅용)
                if (result.intent) {
                    this.addBotMessage(`💡 인식된 의도: ${result.intent}`);
                }
            }
            
        } catch (error) {
            this.addBotMessage('❌ 챗봇 처리 중 오류가 발생했습니다: ' + error.message);
            this.addBotMessage('💡 백엔드 서버가 실행 중인지 확인해주세요');
        } finally {
            this.showLoading(false);
        }
    }
    
    parseUserRequest(message) {
        // 회사명 추출 패턴
        const companyPatterns = [
            /([가-힣a-zA-Z0-9]+)에서/,
            /([가-힣a-zA-Z0-9]+)이\s/,
            /([가-힣a-zA-Z0-9]+)가\s/,
            /([가-힣a-zA-Z0-9]+)\s.*?([말했|했어|답변|거절|반박])/
        ];
        
        let companyName = '';
        for (const pattern of companyPatterns) {
            const match = message.match(pattern);
            if (match) {
                companyName = match[1];
                break;
            }
        }
        
        // 담당자 추출 (선택사항)
        const namePatterns = [
            /([가-힣]{2,4})\s*(대표|팀장|매니저|담당자|님)/,
            /([가-힣]{2,4})\s*씨/
        ];
        
        let emailName = '';
        for (const pattern of namePatterns) {
            const match = message.match(pattern);
            if (match) {
                emailName = match[0];
                break;
            }
        }
        
        // 전체 메시지를 컨텍스트로 사용 (회사명 제거)
        let context = message;
        if (companyName) {
            context = message.replace(new RegExp(companyName, 'g'), '{회사명}');
        }
        
        return {
            companyName,
            emailName,
            context: message // 원본 전체를 컨텍스트로
        };
    }

    async generateChatReply() {
        // 챗봇 모드: 부정적 답변에 대한 재설득 메일 생성
        const companyName = document.getElementById('chatCompanyName')?.value.trim();
        const emailName = document.getElementById('chatEmailName')?.value.trim();
        const context = document.getElementById('chatContext')?.value.trim();
        
        if (!context) {
            this.addBotMessage('❌ 고객의 답변 또는 상황을 입력해주세요.');
            return;
        }
        
        if (!companyName) {
            this.addBotMessage('❌ 회사명을 입력해주세요.');
            return;
        }
        
        this.showLoading(true);
        this.addBotMessage(`💬 ${companyName}님의 상황을 분석하여 재설득 메일을 생성하고 있습니다...`);
        
        try {
            const response = await fetch('/api/chat-reply', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    context: context,
                    company_name: companyName,
                    email_name: emailName || '담당자님'
                })
            });
            
            if (!response.ok) {
                throw new Error(`API 오류: ${response.status}`);
            }
            
            const result = await response.json();
            
            if (result.success) {
                this.displayChatReply(result.email, companyName);
                this.addBotMessage(`✅ ${companyName}님을 위한 재설득 메일이 생성되었습니다!`);
                
                // 전략 설명
                if (result.email.strategy_used) {
                    this.addBotMessage(`📋 사용된 전략: ${result.email.strategy_used}`);
                }
                
                // 핵심 포인트
                if (result.email.key_points && result.email.key_points.length > 0) {
                    const points = result.email.key_points.map((p, i) => `${i+1}. ${p}`).join('<br>');
                    this.addBotMessage(`🎯 핵심 포인트:<br>${points}`);
                }
            } else {
                throw new Error(result.error || '알 수 없는 오류');
            }
            
        } catch (error) {
            this.addBotMessage('❌ 재설득 메일 생성 중 오류가 발생했습니다: ' + error.message);
            this.addBotMessage('💡 백엔드 서버가 실행 중인지 확인해주세요 (python app.py)');
        } finally {
            this.showLoading(false);
        }
    }
    
    displayChatReply(email, companyName) {
        const container = document.getElementById('templatesContainer');
        container.innerHTML = '';
        
        const emailCard = document.createElement('div');
        emailCard.className = 'email-template';
        
        emailCard.innerHTML = `
            <div class="d-flex justify-content-between align-items-start mb-3">
                <div>
                    <h5 class="mb-1">
                        <i class="fas fa-reply text-info"></i> 재설득 메일
                    </h5>
                    <span class="badge bg-info">챗봇 생성</span>
                    <span class="badge bg-light text-dark">${companyName}</span>
                </div>
                <div>
                    <button class="btn btn-sm btn-outline-primary me-2" onclick="copyChatEmail('${companyName}')">
                        <i class="fas fa-copy"></i> 복사
                    </button>
                    <button class="btn btn-sm btn-outline-success" onclick="saveChatEmail('${companyName}')">
                        <i class="fas fa-save"></i> 저장
                    </button>
                </div>
            </div>
            
            <div class="mb-3">
                <strong>제목:</strong>
                <div class="p-2 bg-light rounded mt-1" id="chat-subject-${companyName}">
                    ${email.subject}
                </div>
            </div>
            
            <div>
                <strong>본문:</strong>
                <div class="p-3 bg-light rounded mt-1" id="chat-body-${companyName}">
                    ${email.body}
                </div>
            </div>
        `;
        
        container.appendChild(emailCard);
        document.getElementById('templatesSection').style.display = 'block';
        
        // 스크롤 이동
        emailCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    displayGeneratedEmails(variations, salesPoint) {
        // 판매 상품 변경으로 재생성된 메일 표시
        const container = document.getElementById('templatesContainer');
        container.innerHTML = '';
        
        const salesPointLabel = {
            'opi': 'One Payment Infra',
            'recon': '재무자동화',
            '인앱수수료절감': '게임 웹상점 (인앱수수료절감)'
        }[salesPoint] || salesPoint;
        
        container.innerHTML = `
            <div class="alert alert-success mb-3">
                <i class="fas fa-check-circle"></i> <strong>${salesPointLabel}</strong> 제품으로 메일을 재생성했습니다!
            </div>
        `;
        
        // 각 variation 표시
        Object.entries(variations).forEach(([key, email]) => {
            const emailCard = document.createElement('div');
            emailCard.className = 'email-template mb-3';
            
            const typeLabel = {
                'opi_professional': 'OPI 전문적',
                'opi_curiosity': 'OPI 호기심',
                'finance_professional': '재무 전문적',
                'finance_curiosity': '재무 호기심',
                'game_d2c_professional': '게임 D2C 전문적',
                'game_d2c_curiosity': '게임 D2C 호기심'
            }[key] || key;
            
            emailCard.innerHTML = `
                <div class="d-flex justify-content-between align-items-start mb-3">
                    <div>
                        <h5 class="mb-1">
                            <i class="fas fa-envelope text-primary"></i> ${typeLabel}
                        </h5>
                        <span class="badge bg-primary">재생성</span>
                    </div>
                    <div>
                        <button class="btn btn-sm btn-outline-primary me-2" onclick="copyEmail('${key}')">
                            <i class="fas fa-copy"></i> 복사
                        </button>
                    </div>
                </div>
                
                <div class="mb-3">
                    <strong>제목:</strong>
                    <div class="p-2 bg-light rounded mt-1" id="subject-${key}">
                        ${email.subject}
                    </div>
                </div>
                
                <div>
                    <strong>본문:</strong>
                    <div class="p-3 bg-light rounded mt-1" style="word-break: keep-all; line-break: strict; line-height: 1.8;" id="body-${key}">
                        ${convertMarkdownToHtml(email.body)}
                    </div>
                </div>
            `;
            
            container.appendChild(emailCard);
        });
        
        document.getElementById('templatesSection').style.display = 'block';
        container.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    displayRefinedEmail(email) {
        // 톤 변경 또는 개선된 메일 표시
        const container = document.getElementById('templatesContainer');
        container.innerHTML = '';
        
        const emailCard = document.createElement('div');
        emailCard.className = 'email-template';
        
        emailCard.innerHTML = `
            <div class="d-flex justify-content-between align-items-start mb-3">
                <div>
                    <h5 class="mb-1">
                        <i class="fas fa-magic text-success"></i> 개선된 메일
                    </h5>
                    <span class="badge bg-success">개선 완료</span>
                </div>
                <div>
                    <button class="btn btn-sm btn-outline-primary me-2" onclick="copyRefinedEmail()">
                        <i class="fas fa-copy"></i> 복사
                    </button>
                </div>
            </div>
            
            <div class="mb-3">
                <strong>제목:</strong>
                <div class="p-2 bg-light rounded mt-1" id="refined-subject">
                    ${email.subject}
                </div>
            </div>
            
            <div>
                <strong>본문:</strong>
                <div class="p-3 bg-light rounded mt-1" style="word-break: keep-all; line-break: strict; line-height: 1.8;" id="refined-body">
                    ${convertMarkdownToHtml(email.body)}
                </div>
            </div>
        `;
        
        container.appendChild(emailCard);
        document.getElementById('templatesSection').style.display = 'block';
        
        // 스크롤 이동
        emailCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    addProgressIndicator(total) {
        const chatContainer = document.getElementById('chatContainer');
        const progressDiv = document.createElement('div');
        progressDiv.id = 'progressIndicator';
        progressDiv.className = 'message bot-message';
        progressDiv.innerHTML = `
            <strong>PortOne 메일 봇</strong><br>
            <div class="progress mb-2" style="height: 25px;">
                <div class="progress-bar progress-bar-striped progress-bar-animated bg-primary" 
                     role="progressbar" style="width: 0%" id="progressBar">
                    <span id="progressText">준비 중...</span>
                </div>
            </div>
            <small class="text-muted">병렬 처리로 빠르게 생성 중입니다... ⚡</small>
        `;
        chatContainer.appendChild(progressDiv);
        chatContainer.scrollTop = chatContainer.scrollHeight;
        
        // 가상의 진행률 업데이트 (실제로는 백엔드에서 실시간 업데이트가 어려움)
        this.simulateProgress(total);
    }

    simulateProgress(total) {
        const progressBar = document.getElementById('progressBar');
        const progressText = document.getElementById('progressText');
        
        if (!progressBar || !progressText) return;
        
        // 회사당 평균 처리 시간 (초) - 병렬 처리 고려
        const avgTimePerCompany = 15;
        const maxWorkers = 3; // 동시 처리 개수
        
        // 예상 총 시간 계산 (병렬 처리 고려)
        const estimatedTotalTime = Math.ceil(total / maxWorkers) * avgTimePerCompany;
        
        // 시작 시간 기록
        const startTime = Date.now();
        this.progressStartTime = startTime;
        
        let progress = 0;
        
        const interval = setInterval(() => {
            // 경과 시간 계산
            const elapsedTime = (Date.now() - startTime) / 1000; // 초 단위
            const remainingTime = Math.max(0, estimatedTotalTime - elapsedTime);
            
            // 시간 기반 진행률 계산 (90%까지)
            const timeBasedProgress = Math.min(90, (elapsedTime / estimatedTotalTime) * 90);
            
            // 부드러운 증가를 위해 현재 진행률에서 목표까지 점진적으로 이동
            const targetProgress = timeBasedProgress;
            const diff = targetProgress - progress;
            progress += diff * 0.1; // 10%씩 따라가기
            
            // 진행률 업데이트
            progressBar.style.width = `${progress}%`;
            
            // 남은 시간 표시
            const minutes = Math.floor(remainingTime / 60);
            const seconds = Math.floor(remainingTime % 60);
            
            if (progress < 90) {
                if (remainingTime > 60) {
                    progressText.textContent = `${Math.round(progress)}% (약 ${minutes}분 ${seconds}초 남음)`;
                } else if (remainingTime > 0) {
                    progressText.textContent = `${Math.round(progress)}% (약 ${seconds}초 남음)`;
                } else {
                    progressText.textContent = `${Math.round(progress)}% (완료 중...)`;
                }
            } else {
                progressText.textContent = `${Math.round(progress)}% (거의 완료...)`;
            }
        }, 200); // 더 부드러운 업데이트 (200ms)
        
        // 인스턴스에 저장하여 나중에 정리할 수 있도록
        this.progressInterval = interval;
    }

    removeProgressIndicator() {
        // 진행률을 100%로 완료 표시
        const progressBar = document.getElementById('progressBar');
        const progressText = document.getElementById('progressText');
        
        if (progressBar && progressText) {
            progressBar.style.width = '100%';
            progressText.textContent = '100% 완료! ✅';
            progressBar.classList.remove('progress-bar-animated');
            progressBar.classList.add('bg-success');
        }
        
        // 타이머 정리
        if (this.progressInterval) {
            clearInterval(this.progressInterval);
            this.progressInterval = null;
        }
        
        // 1초 후에 progress indicator 제거 (사용자가 100% 완료를 볼 수 있도록)
        setTimeout(() => {
            const progressElement = document.getElementById('progressIndicator');
            if (progressElement) {
                progressElement.remove();
            }
        }, 1500);
    }

    analyzeCompanyProfile(company) {
        const companyName = company['회사명'] || '';
        const website = company['홈페이지링크'] || company['대표홈페이지'] || '';
        const serviceType = company['서비스유형'] || '';
        
        // 업종 분류
        let industry = 'default';
        const serviceTypeLower = serviceType.toLowerCase();
        if (serviceTypeLower.includes('이커머스') || serviceTypeLower.includes('쇼핑')) {
            industry = 'ecommerce';
        } else if (serviceTypeLower.includes('핀테크') || serviceTypeLower.includes('금융')) {
            industry = 'fintech';
        } else if (serviceTypeLower.includes('saas') || serviceTypeLower.includes('구독')) {
            industry = 'saas';
        } else if (serviceTypeLower.includes('게임') || serviceTypeLower.includes('gaming') || 
                   serviceTypeLower.includes('모바일게임') || serviceTypeLower.includes('온라인게임')) {
            industry = 'gaming';
        } else if (serviceTypeLower.includes('스타트업')) {
            industry = 'startup';
        }
        
        // 회사 규모 추정
        let size = 'sme';
        if (companyName.includes('스타트업') || companyName.length < 5) {
            size = 'startup';
        } else if (companyName.includes('그룹') || companyName.includes('코퍼레이션')) {
            size = 'enterprise';
        }
        
        return {
            industry,
            size,
            painPoints: this.industryPainPoints[industry] || this.industryPainPoints.default,
            website
        };
    }

    async simulateRecentInfoCollection(company) {
        // 실제로는 뉴스 API, 웹 스크래핑 등을 통해 최신 정보 수집
        // 여기서는 시뮬레이션
        const recentInfoTemplates = [
            `${company['회사명']}이 최근 디지털 전환을 가속화하고 있다는 소식을 확인했습니다.`,
            `${company['회사명']}의 온라인 서비스 확장 계획이 발표되었습니다.`,
            `${company['회사명']}이 고객 경험 개선에 투자를 늘리고 있다고 합니다.`,
            `${company['회사명']}의 결제 시스템 개선 필요성이 대두되고 있습니다.`
        ];
        
        return {
            recentNews: recentInfoTemplates[Math.floor(Math.random() * recentInfoTemplates.length)],
            lastUpdated: new Date().toLocaleDateString('ko-KR'),
            source: '업계 동향 분석'
        };
    }

    generateEmailVariations(company, profile, recentInfo) {
        const companyName = company['회사명'];
        // N열(14번째 열)의 호칭 포함 담당자명을 우선 참조
        const contactName = company[Object.keys(company)[13]] || company['담당자명'] || company['대표자명'] || '담당자';
        const contactPosition = company['직책'] || company['직급'] || '';
        const email = company['메일주소'] || company['대표이메일'];
        
        const variations = [];
        
        // 개인화된 인사말 생성
        const personalizedGreeting = this.generatePersonalizedGreeting(contactName, contactPosition, companyName);
        
        // 1. 호기심 유발형 (Zendesk 모범 사례)
        variations.push({
            type: '호기심 유발형',
            subject: this.generateCuriositySubject(companyName, profile, contactName),
            body: this.generateCuriosityBody(companyName, personalizedGreeting, profile, recentInfo),
            personalizationScore: this.calculatePersonalizationScore(company, profile, recentInfo, 'curiosity')
        });
        
        // 2. 가치 제안 중심형
        variations.push({
            type: '가치 제안 중심형',
            subject: this.generateValueSubject(companyName, profile, contactName),
            body: this.generateValueBody(companyName, personalizedGreeting, profile, recentInfo),
            personalizationScore: this.calculatePersonalizationScore(company, profile, recentInfo, 'value')
        });
        
        // 3. 문제 해결형
        variations.push({
            type: '문제 해결형',
            subject: this.generateProblemSolvingSubject(companyName, profile, contactName),
            body: this.generateProblemSolvingBody(companyName, personalizedGreeting, profile, recentInfo),
            personalizationScore: this.calculatePersonalizationScore(company, profile, recentInfo, 'problem')
        });
        
        return variations;
    }

    generatePersonalizedGreeting(contactName, contactPosition, companyName) {
        // 이름과 직책을 활용한 개인화된 인사말 생성
        let greeting = '';
        
        if (contactName && contactName !== '담당자') {
            // 직책이 있는 경우
            if (contactPosition) {
                // 직책에 따른 존칭 처리
                if (contactPosition.includes('대표') || contactPosition.includes('CEO') || contactPosition.includes('사장')) {
                    greeting = `안녕하세요, ${companyName} ${contactPosition} ${contactName}님.`;
                } else if (contactPosition.includes('이사') || contactPosition.includes('부장') || contactPosition.includes('팀장') || contactPosition.includes('매니저')) {
                    greeting = `안녕하세요, ${companyName} ${contactPosition} ${contactName}님.`;
                } else {
                    greeting = `안녕하세요, ${companyName} ${contactPosition} ${contactName}님.`;
                }
            } else {
                // 직책 정보가 없는 경우 이름만으로 인사
                if (contactName.includes('대표') || contactName.includes('CEO') || contactName.includes('사장')) {
                    greeting = `안녕하세요, ${companyName} ${contactName}님.`;
                } else {
                    greeting = `안녕하세요, ${companyName} ${contactName} 담당자님.`;
                }
            }
        } else {
            // 이름 정보가 없는 경우 기본 인사말
            greeting = `안녕하세요, ${companyName} 담당자님.`;
        }
        
        return greeting;
    }

    generateCuriositySubject(companyName, profile, contactName) {
        const contact = contactName && contactName !== '담당자' ? contactName : '담당자님';
        return `[PortOne] ${companyName} ${contact}께 전달 부탁드립니다`;
    }

    generateCuriosityBody(companyName, personalizedGreeting, profile, recentInfo) {
        const painPoint = profile.painPoints[Math.floor(Math.random() * profile.painPoints.length)];
        const valueProps = Object.values(this.portOneValueProps).filter(prop => 
            prop.industries.includes('all') || 
            prop.industries.includes(profile.industry) ||
            prop.industries.includes(profile.size)
        );
        const selectedProp = valueProps[Math.floor(Math.random() * valueProps.length)];
        
        return `${personalizedGreeting}

${recentInfo.recentNews}

${companyName}에서 ${painPoint}으로 고민이 많으실 것 같습니다.

포트원의 One Payment Infra로 ${selectedProp.description}할 수 있습니다.

✅ 2주 내 구축 완료
✅ 85% 리소스 절감  
✅ 100만원 상당 무료 컨설팅

${companyName}에 맞는 결제 인프라 구축 방안을 15분 통화로 설명드릴 수 있을까요?

포트원 드림`;
    }

    generateValueSubject(companyName, profile, contactName) {
        const contact = contactName && contactName !== '담당자' ? contactName : '담당자님';
        return `[PortOne] ${companyName} ${contact}께 전달 부탁드립니다`;
    }

    generateValueBody(companyName, personalizedGreeting, profile, recentInfo) {
        return `${personalizedGreeting}

${recentInfo.recentNews}

${companyName}의 성장에 필요한 결제 인프라, 직접 구축하시려고 하시나요?

포트원과 함께라면:
🚀 개발 기간: 3개월 → 2주
💰 개발 비용: 85% 절감
⚡ 유지보수: 포트원이 전담

실제 고객 사례:
• A사: 결제 개발 기간 90% 단축
• B사: 개발 인력 3명 → 핵심 비즈니스로 재배치
• C사: 결제 전환율 15% 향상

${companyName}도 동일한 결과를 얻을 수 있습니다.

무료 컨설팅으로 구체적인 절약 효과를 계산해드릴까요?

포트원 드림`;
    }

    generateProblemSolvingSubject(companyName, profile, contactName) {
        const contact = contactName && contactName !== '담당자' ? contactName : '담당자님';
        return `[PortOne] ${companyName} ${contact}께 전달 부탁드립니다`;
    }

    generateProblemSolvingBody(companyName, personalizedGreeting, profile, recentInfo) {
        const painPoint = profile.painPoints[Math.floor(Math.random() * profile.painPoints.length)];
        
        return `${personalizedGreeting}

${recentInfo.recentNews}

${companyName}에서 ${painPoint} 때문에 고민이 많으시죠?

이런 문제들 때문에 많은 회사들이 포트원을 선택합니다:

❌ 복잡한 PG 연동 과정
❌ 높은 개발 및 유지보수 비용  
❌ 결제 장애 시 대응의 어려움
❌ 여러 PG사 관리의 복잡성

✅ 포트원 솔루션:
• 단 한 번의 연동으로 모든 PG 관리
• 개발 리소스 85% 절감
• 24/7 전문가 기술 지원
• 스마트 라우팅으로 안정성 확보

${companyName}의 현재 결제 환경을 분석해서 맞춤 해결책을 제안드리겠습니다.

15분 통화 가능하실까요?

포트원 드림`;
    }

    calculatePersonalizationScore(company, profile, recentInfo, type) {
        let score = 5; // 기본 점수
        
        // 회사명 활용 (+1점)
        score += 1;
        
        // 최신 정보 활용 (+2점)
        if (recentInfo.recentNews) score += 2;
        
        // 업종별 특화 (+1점)
        if (profile.industry !== 'default') score += 1;
        
        // 타입별 보너스
        if (type === 'curiosity') score += 0.5;
        if (type === 'value') score += 1;
        if (type === 'problem') score += 0.5;
        
        return Math.min(10, Math.round(score * 10) / 10);
    }

    displayAIGeneratedTemplates(results) {
        console.log('=== displayAIGeneratedTemplates 시작 ===');
        console.log('받은 results:', results);
        console.log('results 길이:', results?.length);
        
        const container = document.getElementById('templatesContainer');
        container.innerHTML = '';
        
        if (!results || results.length === 0) {
            console.error('❌ results가 비어있음!');
            container.innerHTML = '<div class="alert alert-danger">이메일 생성 결과가 없습니다.</div>';
            return;
        }
        
        // 결과를 인스턴스 변수에 저장하여 CSV 다운로드에서 사용
        this.generatedResults = results;
        
        // 자동 저장: 모든 결과를 localStorage에 저장
        this.autoSaveSession(results);
        
        results.forEach((result, index) => {
            console.log(`회사 ${index + 1} 처리 중:`, result.company?.['회사명']);
            console.log('result.emails:', result.emails);
            console.log('result.emails.variations:', result.emails?.variations);
            
            if (result.error) {
                // 오류가 있는 경우
                console.error(`회사 ${index + 1} 오류:`, result.error);
                const errorDiv = document.createElement('div');
                errorDiv.className = 'company-templates mb-4';
                errorDiv.innerHTML = `
                    <div class="alert alert-warning">
                        <h6><i class="fas fa-exclamation-triangle"></i> ${result.company['회사명']}</h6>
                        <p class="mb-0">처리 중 오류: ${result.error}</p>
                    </div>
                `;
                container.appendChild(errorDiv);
                return;
            }

            const companyDiv = document.createElement('div');
            companyDiv.className = 'company-templates mb-4';
            
            // SSR 정보 확인
            const ssrEnabled = result.emails?.ssr_enabled || false;
            const recommendedEmail = result.emails?.recommended_email;
            const allRankedEmails = result.emails?.all_ranked_emails;
            const selectedCases = result.selected_cases || [];
            
            // AI가 생성한 메일 문안 파싱 (개선된 버전)
            let emailVariations = [];
            if (result.emails && result.emails.success) {
                try {
                    const variations = result.emails.variations;
                    
                    // 먼저 JSON 파싱 시도
                    let parsedVariations = null;
                    if (typeof variations === 'string') {
                        try {
                            // JSON 문자열인 경우 파싱
                            parsedVariations = JSON.parse(variations);
                        } catch (jsonError) {
                            // JSON 파싱 실패 시 텍스트에서 JSON 추출 시도
                            const jsonMatch = variations.match(/\{[\s\S]*\}/);
                            if (jsonMatch) {
                                try {
                                    parsedVariations = JSON.parse(jsonMatch[0]);
                                } catch (extractError) {
                                    console.log('JSON 추출 실패:', extractError);
                                }
                            }
                        }
                    } else if (typeof variations === 'object' && !variations.raw_content) {
                        parsedVariations = variations;
                    }
                    
                    if (parsedVariations && typeof parsedVariations === 'object') {
                        // 성공적으로 파싱된 JSON 객체 처리 (4개 이메일 구조)
                        emailVariations = Object.entries(parsedVariations).map(([key, value]) => {
                            // 각 스타일별 한국어 이름 매핑 (4개 이메일)
                            const typeNames = {
                                'opi_professional': 'OPI - 전문적 톤',
                                'opi_curiosity': 'OPI - 호기심 유발형',
                                'finance_professional': '재무자동화 - 전문적 톤',
                                'finance_curiosity': '재무자동화 - 호기심 유발형',
                                'prism_professional': 'Prism - 전문적 톤',
                                'prism_curiosity': 'Prism - 호기심 유발형',
                                'game_d2c_professional': '게임 D2C - 전문적 톤',
                                'game_d2c_curiosity': '게임 D2C - 호기심 유발형',
                                // 기존 호환성
                                'professional': '전문적 톤',
                                'curiosity': '호기심 유발형',
                                'value': '가치 제안형',
                                'problem': '문제 해결형'
                            };
                            
                            return {
                                type: typeNames[key] || key,
                                originalKey: key,
                                product: value.product || 'PortOne 솔루션',
                                subject: value.subject || '제목 없음',
                                body: value.body || '본문 없음',
                                cta: value.cta || '',
                                tone: value.tone || '',
                                personalizationScore: value.personalization_score || this.calculateAIScore(result.research, value)
                            };
                        });
                        
                        // SSR 활성화된 경우 순위 정보 추가
                        if (ssrEnabled && allRankedEmails && allRankedEmails.length > 0) {
                            // SSR 점수 기반으로 emailVariations 재정렬 및 점수 추가
                            emailVariations = emailVariations.map(email => {
                                const rankedEmail = allRankedEmails.find(r => r.type === email.originalKey);
                                if (rankedEmail) {
                                    return {
                                        ...email,
                                        ssrScore: rankedEmail.ssr_score || 0,
                                        ssrConfidence: rankedEmail.ssr_confidence || 0,
                                        ssrReasoning: rankedEmail.ssr_reasoning || '',
                                        ssrMethod: rankedEmail.ssr_method || 'unknown',
                                        isRecommended: rankedEmail.type === recommendedEmail?.type
                                    };
                                }
                                return email;
                            });
                            
                            // SSR 점수로 정렬 (높은 점수가 먼저)
                            emailVariations.sort((a, b) => (b.ssrScore || 0) - (a.ssrScore || 0));
                        }
                    } else {
                        // JSON 파싱 실패 시 텍스트를 3개 스타일로 분할 시도
                        const textContent = variations.raw_content || variations || '';
                        emailVariations = this.parseTextToVariations(textContent, result.company['회사명']);
                    }
                } catch (e) {
                    console.error('이메일 파싱 오류:', e);
                    // 완전 실패 시 기본 템플릿 제공
                    // N열(14번째 열)의 호칭 포함 담당자명을 우선 참조
                    const contactName = result.company[Object.keys(result.company)[13]] || result.company['담당자명'] || result.company['대표자명'] || '담당자';
                    const contactPosition = result.company['직책'] || result.company['직급'] || '';
                    const personalizedGreeting = this.generatePersonalizedGreeting(contactName, contactPosition, result.company['회사명']);
                    emailVariations = this.createFallbackVariations(result.company['회사명'], personalizedGreeting);
                }
            }
            
            // 이메일 주소 추출 (다양한 컬럼명 지원)
            const possibleEmailColumns = [
                '대표이메일', '이메일', '회사이메일', '담당자이메일', 
                'email', 'Email', 'EMAIL', 'e-mail', 'E-mail', 'E-MAIL',
                '메일', '메일주소', '이메일주소', 'mail', 'Mail', 'MAIL'
            ];
            
            let emailAddress = '';
            for (const column of possibleEmailColumns) {
                if (result.company[column] && result.company[column].trim() !== '') {
                    emailAddress = result.company[column].trim();
                    console.log(`이메일 주소 발견: ${column} = ${emailAddress}`);
                    break;
                }
            }
            
            // 디버깅: CSV 컬럼 확인
            console.log('=== 이메일 디버깅 시작 ===');
            console.log('CSV 컬럼들:', Object.keys(result.company));
            console.log('대표이메일 값:', result.company['대표이메일']);
            console.log('전체 회사 데이터:', result.company);
            
            // 모든 가능한 이메일 컬럼 값 확인
            possibleEmailColumns.forEach(column => {
                const value = result.company[column];
                console.log(`${column}: "${value}" (타입: ${typeof value})`);
            });
            
            console.log('최종 선택된 이메일 주소:', emailAddress);
            console.log('=== 이메일 디버깅 끝 ===');
            
            companyDiv.innerHTML = `
                <div class="company-info">
                    <h5><i class="fas fa-building"></i> ${result.company['회사명']}</h5>
                    ${emailAddress ? `
                        <p class="mb-2" style="background-color: #f8f9fa; padding: 8px; border-radius: 4px; border-left: 3px solid #007bff;">
                            <i class="fas fa-envelope text-primary"></i> <strong>대표이메일:</strong> 
                            <a href="mailto:${emailAddress}" class="text-primary text-decoration-none" title="메일 보내기" style="font-weight: 500;">
                                ${emailAddress}
                            </a>
                        </p>
                    ` : `
                        <p class="mb-2 text-muted">
                            <i class="fas fa-envelope-open"></i> <small>이메일 정보 없음</small>
                        </p>
                    `}
                    <div class="row">
                        <div class="col-md-6">
                            <small><strong>🔍 Perplexity 조사:</strong> ${result.research.success ? '완료' : '실패'}</small><br>
                            <small><strong>✍️ Claude 문안 생성:</strong> ${result.emails.success ? '완료' : '실패'}</small>
                        </div>
                        <div class="col-md-6">
                            <small><strong>조사 시간:</strong> ${new Date(result.research.timestamp).toLocaleTimeString('ko-KR')}</small><br>
                            <small><strong>생성 시간:</strong> ${new Date(result.emails.timestamp).toLocaleTimeString('ko-KR')}</small>
                        </div>
                    </div>
                    ${result.research.company_info ? `
                        <div class="mt-2">
                            <small><strong>🔍 조사 결과:</strong></small>
                            <div class="small text-muted research-content" style="max-height: 300px; overflow-y: auto; white-space: pre-wrap; border: 1px solid #e9ecef; padding: 10px; border-radius: 5px; background-color: #f8f9fa;">
                                ${result.research.company_info}
                            </div>
                            <div class="d-flex gap-2 mt-2">
                                <button class="btn btn-sm btn-outline-primary" onclick="toggleResearchContent(this)">
                                    <i class="fas fa-expand-alt"></i> 전체 내용 보기
                                </button>
                                <button class="btn btn-sm btn-success" onclick="saveAllEmailsForCompany(${index})">
                                    <i class="fas fa-save"></i> 이 회사 전체 저장
                                </button>
                            </div>
                        </div>
                    ` : ''}
                </div>
                
                ${ssrEnabled && selectedCases.length > 0 ? `
                    <div class="alert alert-info mt-2">
                        <strong><i class="fas fa-lightbulb"></i> 적용된 실제 사례:</strong>
                        <small class="d-block mt-1">${selectedCases.join(', ')}</small>
                    </div>
                ` : ''}
                
                ${ssrEnabled ? `
                    <div class="alert alert-success mt-2">
                        <strong><i class="fas fa-chart-line"></i> SSR 기반 최적화 완료</strong>
                        <p class="mb-0 small">논문 기반 Semantic Similarity Rating으로 가장 효과적인 이메일을 선정했습니다.</p>
                    </div>
                ` : ''}
                
                <div class="row">
                    ${emailVariations.map((variation, vIndex) => `
                        <div class="col-md-${emailVariations.length === 1 ? '12' : '6'} mb-3">
                            <div class="email-template ${variation.isRecommended ? 'border-success border-3' : ''}" style="position: relative;">
                                ${emailAddress ? `
                                    <div class="form-check position-absolute" style="top: 10px; left: 10px; z-index: 10;">
                                        <input class="form-check-input" type="checkbox" 
                                               id="email_select_${index}_${vIndex}"
                                               data-company-index="${index}"
                                               data-variation-index="${vIndex}"
                                               data-company-name="${result.company['회사명']}"
                                               data-email="${emailAddress}"
                                               data-subject="${variation.subject.replace(/"/g, '&quot;')}"
                                               data-body="${variation.body.replace(/"/g, '&quot;').replace(/\n/g, '\\n')}"
                                               onchange="updateSelectedCount()">
                                        <label class="form-check-label" for="email_select_${index}_${vIndex}" style="font-size: 0.85em;">
                                            발송 선택
                                        </label>
                                    </div>
                                ` : ''}
                                ${variation.hallucination_warning ? `
                                    <div class="alert alert-warning mb-3" style="margin-left: ${emailAddress ? '100px' : '0'}; border-left: 4px solid #ffc107;">
                                        <i class="fas fa-exclamation-triangle"></i> <strong>환각 가능성 경고</strong><br>
                                        <small>${variation.warning_message || '⚠️ 이 문안은 사실 확인이 필요할 수 있습니다. Perplexity 조사 결과와 일부 불일치가 감지되었습니다.'}</small>
                                    </div>
                                ` : ''}
                                ${variation.isRecommended ? `
                                    <div class="badge bg-success mb-2" style="margin-left: ${emailAddress ? '100px' : '0'};">
                                        <i class="fas fa-star"></i> AI 추천 (최적 메일)
                                    </div>
                                ` : ''}
                                <div class="d-flex justify-content-between align-items-center mb-2" style="margin-left: ${emailAddress ? '100px' : '0'};">
                                    <h6 class="mb-0">
                                        <i class="fas fa-robot text-primary"></i> ${variation.type}
                                        ${variation.product ? `<br><small class="text-muted">${variation.product}</small>` : ''}
                                    </h6>
                                    <div class="text-end">
                                        ${variation.ssrScore !== undefined ? `
                                            <div class="badge bg-primary mb-1">
                                                SSR: ${variation.ssrScore.toFixed(2)}/5.0
                                            </div>
                                            <br>
                                            <small class="text-muted" title="${variation.ssrReasoning}">
                                                신뢰도: ${(variation.ssrConfidence * 100).toFixed(0)}%
                                            </small>
                                        ` : `
                                            <span class="personalization-score ${this.getScoreClass(variation.personalizationScore)}">
                                                ${variation.personalizationScore}/10
                                            </span>
                                        `}
                                    </div>
                                </div>
                                <div class="mb-2">
                                    <strong>제목:</strong>
                                    <button class="btn btn-sm btn-outline-primary ms-2" onclick="copySubjectFromTextarea(${index}, ${vIndex})">
                                        <i class="fas fa-copy"></i> 제목 복사
                                    </button>
                                    <button class="btn btn-sm btn-outline-info ms-2" onclick="toggleEditMode(${index}, ${vIndex})">
                                        <i class="fas fa-edit"></i> 수정
                                    </button>
                                    <br>
                                    <div id="subject_display_${index}_${vIndex}">
                                        <em>${variation.subject}</em>
                                    </div>
                                    <textarea id="subject_edit_${index}_${vIndex}" class="form-control mt-2" style="display: none;">${variation.subject}</textarea>
                                </div>
                                <div class="mb-3">
                                    <strong>본문:</strong><br>
                                    <div id="body_display_${index}_${vIndex}" style="white-space: pre-line; word-break: keep-all; line-break: strict; font-size: 0.9em; max-height: 300px; overflow-y: auto; border: 1px solid #eee; padding: 10px; border-radius: 5px; line-height: 1.8;">
                                        ${convertMarkdownToHtml(variation.body)}
                                    </div>
                                    <div id="body_edit_${index}_${vIndex}" 
                                         contenteditable="true"
                                         class="form-control mt-2" 
                                         style="display: none; min-height: 200px; max-height: 400px; overflow-y: auto; white-space: pre-wrap; line-height: 1.8;"
                                         data-placeholder="이메일 본문을 입력하세요...">
                                    </div>
                                    <div id="edit_help_${index}_${vIndex}" class="alert alert-success mt-2" style="display: none; font-size: 0.85em;">
                                        <strong><i class="fas fa-magic"></i> 일반 문서처럼 편집하세요!</strong><br>
                                        <small>
                                            • 그냥 입력하시면 됩니다 (특수문자 불필요!)<br>
                                            • Enter로 줄바꿈<br>
                                            • 기존 볼드체는 자동 유지됩니다<br>
                                            • 복사/붙여넣기 가능
                                        </small>
                                    </div>
                                    <div id="edit_buttons_${index}_${vIndex}" class="mt-2" style="display: none;">
                                        <button class="btn btn-sm btn-success" onclick="saveEditedEmail(${index}, ${vIndex})">
                                            <i class="fas fa-save"></i> 저장
                                        </button>
                                        <button class="btn btn-sm btn-secondary" onclick="cancelEditMode(${index}, ${vIndex})">
                                            <i class="fas fa-times"></i> 취소
                                        </button>
                                    </div>
                                </div>
                                <div class="d-flex gap-2 flex-wrap">
                                    <button class="btn btn-sm btn-outline-primary" onclick="copyTemplateFromTextarea(${index}, ${vIndex})">
                                        <i class="fas fa-copy"></i> 본문 복사
                                    </button>
                                    ${emailAddress ? `
                                        <button class="btn btn-sm btn-outline-info" onclick="copyToClipboard('${emailAddress}')" title="이메일 주소 복사">
                                            <i class="fas fa-envelope"></i> 이메일 복사
                                        </button>
                                    ` : `
                                        <button class="btn btn-sm btn-outline-warning" onclick="alert('이메일 주소가 없습니다. CSV 파일의 대표이메일 컬럼을 확인해주세요.')" title="이메일 없음">
                                            <i class="fas fa-exclamation-triangle"></i> 이메일 없음
                                        </button>
                                    `}
                                    <button class="btn btn-sm btn-outline-success" onclick="convertToHtmlTemplateFromTextarea(${index}, ${vIndex})">
                                        <i class="fas fa-code"></i> HTML 템플릿
                                    </button>
                                    <button class="btn btn-sm btn-outline-secondary" onclick="refineEmailCopy(${index}, ${vIndex})">
                                        <i class="fas fa-edit"></i> 개선 요청
                                    </button>
                                    <button class="btn btn-sm btn-outline-warning" onclick="saveEmailDraftFromTextarea(${index}, ${vIndex})">
                                        <i class="fas fa-bookmark"></i> 저장
                                    </button>
                                </div>
                                <textarea id="ai_template_${index}_${vIndex}" style="position: absolute; left: -9999px;">
제목: ${variation.subject}

${variation.body}
                                </textarea>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
            
            container.appendChild(companyDiv);
        });
        
        document.getElementById('templatesSection').style.display = 'block';
        
        // CSV 다운로드 버튼 추가
        this.addDownloadButton(container);
    }

    addDownloadButton(container) {
        const downloadSection = document.createElement('div');
        downloadSection.className = 'text-center mt-4 mb-4 p-3 bg-light rounded';
        downloadSection.innerHTML = `
            <h5><i class="fas fa-download"></i> 결과 다운로드</h5>
            <p class="text-muted">생성된 모든 메일 문안을 원본 CSV에 추가하여 다운로드하세요</p>
            <button class="btn btn-success btn-lg" onclick="window.emailChatbot.downloadCSVWithEmails()">
                <i class="fas fa-file-csv"></i> CSV 파일 다운로드 (메일 문안 포함)
            </button>
        `;
        
        // 일괄 발송 섹션 추가
        const batchSendSection = document.createElement('div');
        batchSendSection.className = 'text-center mt-3 mb-4 p-4 border rounded';
        batchSendSection.style.backgroundColor = '#f0f8ff';
        batchSendSection.innerHTML = `
            <h5><i class="fas fa-paper-plane text-primary"></i> 이메일 일괄 발송</h5>
            <p class="text-muted mb-3">
                체크박스로 원하는 이메일 문안을 선택하고 일괄 발송하세요<br>
                <span id="selectedEmailCount" class="badge bg-secondary">0개 선택됨</span>
            </p>
            <div class="d-flex justify-content-center gap-2">
                <button class="btn btn-success btn-lg" onclick="selectAllRecommendedEmails()">
                    <i class="fas fa-star"></i> AI 추천 문안 일괄 선택
                </button>
                <button id="batchSendButton" class="btn btn-primary btn-lg" onclick="batchSendEmails()" disabled>
                    <i class="fas fa-paper-plane"></i> 일괄 발송 (문안을 선택해주세요)
                </button>
            </div>
        `;
        
        // CSV 다운로드는 맨 위에, 일괄 발송 박스는 맨 아래에 배치
        container.insertBefore(downloadSection, container.firstChild);
        container.appendChild(batchSendSection);
    }

    downloadCSVWithEmails() {
        if (!this.generatedResults || !this.uploadedData) {
            this.addBotMessage('❌ 다운로드할 데이터가 없습니다. 먼저 CSV 파일을 업로드하고 메일 문안을 생성해주세요.');
            return;
        }

        try {
            // CSV 헤더 생성 (원본 + 메일 문안 컬럼들)
            const originalHeaders = Object.keys(this.uploadedData[0]);
            const emailHeaders = ['메일문안1_제목', '메일문안1_본문', '메일문안2_제목', '메일문안2_본문', 
                                '메일문안3_제목', '메일문안3_본문', '메일문안4_제목', '메일문안4_본문'];
            const allHeaders = [...originalHeaders, ...emailHeaders];

            let csvContent = allHeaders.join(',') + '\n';

            // 각 회사 데이터에 메일 문안 추가
            this.uploadedData.forEach((company, index) => {
                const result = this.generatedResults.find(r => r.company['회사명'] === company['회사명']);
                
                // 원본 데이터
                const row = originalHeaders.map(header => {
                    const value = company[header] || '';
                    // CSV 형식에 맞게 따옴표 처리
                    return `"${String(value).replace(/"/g, '""')}"`;
                });

                // 메일 문안 데이터 추가
                if (result && result.emails && result.emails.success) {
                    try {
                        const variations = this.extractEmailVariations(result);
                        
                        // 최대 4개 메일 문안 추가 (부족하면 빈 값)
                        for (let i = 0; i < 4; i++) {
                            if (variations[i]) {
                                row.push(`"${String(variations[i].subject).replace(/"/g, '""')}"`);
                                // HTML을 텍스트로 변환하여 저장
                                const plainTextBody = this.htmlToPlainText(variations[i].body);
                                row.push(`"${String(plainTextBody).replace(/"/g, '""')}"`);
                            } else {
                                row.push('""'); // 빈 제목
                                row.push('""'); // 빈 본문
                            }
                        }
                    } catch (e) {
                        // 메일 파싱 실패 시 빈 값으로 채움
                        for (let i = 0; i < 8; i++) {
                            row.push('""');
                        }
                    }
                } else {
                    // 메일 생성 실패 시 빈 값으로 채움
                    for (let i = 0; i < 8; i++) {
                        row.push('""');
                    }
                }

                csvContent += row.join(',') + '\n';
            });

            // 파일 다운로드
            this.downloadFile(csvContent, `이메일_문안_${new Date().toISOString().slice(0, 10)}.csv`, 'text/csv');
            this.addBotMessage('✅ 메일 문안이 포함된 CSV 파일이 다운로드되었습니다!');
            
        } catch (error) {
            console.error('CSV 다운로드 오류:', error);
            this.addBotMessage('❌ CSV 다운로드 중 오류가 발생했습니다: ' + error.message);
        }
    }

    extractEmailVariations(result) {
        const variations = [];
        
        if (result.emails && result.emails.success) {
            const emailData = result.emails.variations;
            
            // JSON 파싱 시도
            let parsedVariations = null;
            if (typeof emailData === 'string') {
                try {
                    parsedVariations = JSON.parse(emailData);
                } catch (e) {
                    // JSON 문자열에서 추출 시도
                    const jsonMatch = emailData.match(/\{[\s\S]*\}/);
                    if (jsonMatch) {
                        try {
                            parsedVariations = JSON.parse(jsonMatch[0]);
                        } catch (extractError) {
                            console.log('JSON 추출 실패:', extractError);
                        }
                    }
                }
            } else if (typeof emailData === 'object') {
                parsedVariations = emailData;
            }

            if (parsedVariations && typeof parsedVariations === 'object') {
                Object.entries(parsedVariations).forEach(([key, value]) => {
                    variations.push({
                        type: key,
                        subject: value.subject || '',
                        body: value.body || ''
                    });
                });
            }
        }

        return variations;
    }

    htmlToPlainText(html) {
        if (!html) return '';
        
        // HTML 태그 제거 및 특수 문자 변환
        let text = html
            .replace(/<br\s*\/?>/gi, '\n')           // <br> 태그를 줄바꿈으로
            .replace(/<\/p>/gi, '\n\n')              // </p> 태그를 두 줄바꿈으로
            .replace(/<p[^>]*>/gi, '')               // <p> 태그 제거
            .replace(/<\/div>/gi, '\n')              // </div> 태그를 줄바꿈으로
            .replace(/<div[^>]*>/gi, '')             // <div> 태그 제거
            .replace(/<[^>]*>/g, '')                 // 모든 HTML 태그 제거
            .replace(/&nbsp;/g, ' ')                 // &nbsp;를 공백으로
            .replace(/&lt;/g, '<')                   // &lt;를 <로
            .replace(/&gt;/g, '>')                   // &gt;를 >로
            .replace(/&amp;/g, '&')                  // &amp;를 &로
            .replace(/&quot;/g, '"')                 // &quot;를 "로
            .replace(/&#39;/g, "'")                  // &#39;를 '로
            .replace(/\n\s*\n/g, '\n\n')            // 연속된 빈 줄을 두 줄로 제한
            .trim();                                 // 앞뒤 공백 제거
            
        return text;
    }

    downloadFile(content, fileName, mimeType) {
        const blob = new Blob(['\ufeff' + content], { type: mimeType + ';charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = fileName;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    // 뉴스 분석 결과로 기존 문안 덮어쓰기
    displayNewsAnalysisResult(result, request, newsUrl) {
        console.log('📰 뉴스 분석 결과 덮어쓰기 시작');
        
        // 현재 refinement target 가져오기
        const { companyIndex, variationIndex } = this.currentRefinementTarget;
        
        // 기존 문안을 뉴스 분석 결과로 덮어쓰기
        this.updateExistingVariation(companyIndex, variationIndex, result.analyzed_email, request);
        
        // 챗봇에 추가 정보 표시
        if (result.article_summary) {
            this.addBotMessage(`📋 기사 요약:\n${result.article_summary.substring(0, 300)}...`);
        }
        
        if (result.pain_points && result.pain_points.length > 0) {
            this.addBotMessage(`🎯 발굴된 페인 포인트:\n${result.pain_points.join('\n')}`);
        }
        
        // 뉴스 URL 표시
        let newsDomain = '';
        try {
            const url = new URL(newsUrl);
            newsDomain = url.hostname;
        } catch (e) {
            newsDomain = newsUrl;
        }
        this.addBotMessage(`🔗 참고 기사: ${newsDomain}`);
    }

    // 개선된 이메일로 기존 문안 덮어쓰기
    updateExistingVariation(companyIndex, variationIndex, refinedEmail, request) {
        console.log('🔄 덮어쓰기 시작:', { companyIndex, variationIndex, refinedEmailLength: refinedEmail.length });
        
        // 1. 데이터 업데이트 (generatedResults)
        if (this.generatedResults && this.generatedResults[companyIndex]) {
            const result = this.generatedResults[companyIndex];
            if (result.emails && result.emails.variations) {
                const variationKeys = Object.keys(result.emails.variations);
                const targetKey = variationKeys[variationIndex];
                if (targetKey && result.emails.variations[targetKey]) {
                    // 제목과 본문 분리 (제목: 으로 시작하는 경우)
                    let subject = result.emails.variations[targetKey].subject;
                    let body = refinedEmail;
                    
                    const lines = refinedEmail.split('\n');
                    if (lines[0] && lines[0].startsWith('제목:')) {
                        subject = lines[0].replace('제목:', '').trim();
                        body = lines.slice(1).join('\n').trim();
                    }
                    
                    result.emails.variations[targetKey].subject = subject;
                    result.emails.variations[targetKey].body = body;
                    console.log('✅ 데이터 업데이트 완료:', targetKey);
                }
            }
        }
        
        // 2. UI 업데이트 - 해당 variation의 본문 영역 찾아서 교체
        const variationElement = document.querySelector(`#ai_template_${companyIndex}_${variationIndex}`);
        console.log('🔍 Element 검색:', `#ai_template_${companyIndex}_${variationIndex}`, variationElement ? '찾음' : '못 찾음');
        
        if (variationElement) {
            // textarea 값 업데이트
            variationElement.value = refinedEmail;
            
            // 화면에 표시되는 본문 영역 업데이트
            const parentTemplate = variationElement.closest('.email-template');
            if (parentTemplate) {
                const bodyDisplay = parentTemplate.querySelector('div[style*="white-space: pre-line"]');
                if (bodyDisplay) {
                    // 제목과 본문 분리
                    let displayBody = refinedEmail;
                    const lines = refinedEmail.split('\n');
                    if (lines[0] && lines[0].startsWith('제목:')) {
                        const subject = lines[0].replace('제목:', '').trim();
                        displayBody = lines.slice(1).join('\n').trim();
                        
                        // 제목도 업데이트
                        const subjectDisplay = parentTemplate.querySelector('div.mb-2 em');
                        if (subjectDisplay) {
                            subjectDisplay.textContent = subject;
                        }
                    }
                    
                    // 마크다운을 HTML로 변환하여 표시
                    bodyDisplay.innerHTML = convertMarkdownToHtml(displayBody);
                    
                    // 개선됨 표시 추가
                    parentTemplate.style.borderLeft = '4px solid #28a745';
                    parentTemplate.style.backgroundColor = '#f8fff9';
                    
                    // 상단에 개선 완료 배지 추가 (이미 없는 경우에만)
                    const headerDiv = parentTemplate.querySelector('.d-flex.justify-content-between');
                    if (headerDiv && !headerDiv.querySelector('.badge.bg-success')) {
                        const badge = document.createElement('span');
                        badge.className = 'badge bg-success ms-2';
                        badge.innerHTML = '<i class="fas fa-check"></i> 개선됨';
                        headerDiv.querySelector('h6').appendChild(badge);
                    }
                }
            }
        }
        
        // 3. 해당 variation에 ID 추가 (스크롤 대상)
        const targetVariation = document.querySelector(`#ai_template_${companyIndex}_${variationIndex}`)?.closest('.email-template');
        if (targetVariation) {
            targetVariation.id = `variation_${companyIndex}_${variationIndex}`;
        }
        
        // 4. 개선된 내용을 세션에 자동 저장
        if (this.generatedResults) {
            this.autoSaveSession(this.generatedResults);
            console.log('✅ 개선된 문안이 세션에 자동 저장되었습니다.');
        }
    }
    
    // 특정 variation으로 스크롤 이동
    scrollToVariation(companyIndex, variationIndex) {
        const targetElement = document.getElementById(`variation_${companyIndex}_${variationIndex}`);
        if (targetElement) {
            targetElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
            
            // 강조 효과 추가
            targetElement.style.transition = 'all 0.3s ease';
            targetElement.style.boxShadow = '0 0 20px rgba(40, 167, 69, 0.5)';
            
            setTimeout(() => {
                targetElement.style.boxShadow = '';
            }, 2000);
        }
    }

    getScoreClass(score) {
        if (score >= 8) return 'score-high';
        if (score >= 6) return 'score-medium';
        return 'score-low';
    }

    // 텍스트를 3개 스타일로 분할하는 함수
    parseTextToVariations(textContent, companyName) {
        // 텍스트에서 제목과 본문 추출 시도
        const lines = textContent.split('\n').filter(line => line.trim());
        
        // 기본 3개 스타일 생성
        return [
            {
                type: '전문적 톤',
                subject: `${companyName}의 결제 인프라 혁신 제안`,
                body: this.extractMainContent(textContent, 0),
                personalizationScore: 8.0
            },
            {
                type: '친근한 톤',
                subject: `${companyName}님, 결제 시스템 업그레이드 준비되셨나요?`,
                body: this.extractMainContent(textContent, 1),
                personalizationScore: 7.5
            },
            {
                type: '호기심 유발형',
                subject: `${companyName}의 결제 시스템, 얼마나 효율적인가요?`,
                body: this.extractMainContent(textContent, 2),
                personalizationScore: 8.5
            }
        ];
    }
    
    // 텍스트에서 메인 컨텐츠 추출
    extractMainContent(textContent, styleIndex) {
        // 기본 컨텐츠를 스타일에 맞게 조정
        const baseContent = textContent.substring(0, 500); // 첫 500자만 사용
        
        const styles = [
            '안녕하세요 담당자님,\n\n',
            '안녕하세요! \n\n',
            '혹시 궁금한 게 있어 연락드립니다.\n\n'
        ];
        
        return styles[styleIndex] + baseContent + '\n\n감사합니다.\n\nPortOne 팀 드림';
    }
    
    // 완전 실패 시 기본 템플릿 생성 (4개 이메일)
    createFallbackVariations(companyName, personalizedGreeting = null) {
        // 개인화된 인사말이 없으면 기본 인사말 생성
        if (!personalizedGreeting) {
            personalizedGreeting = `안녕하세요, ${companyName} 담당자님.`;
        }
        return [
            {
                type: 'OPI - 전문적 톤',
                product: 'One Payment Infra',
                subject: `${companyName}의 결제 인프라 혁신 제안`,
                body: `${personalizedGreeting}\n\n귀사의 비즈니스 성장에 깊은 인상을 받았습니다.\n\nPortOne의 One Payment Infra로 85% 리소스 절감과 2주 내 구축이 가능합니다.\n\n15분 통화로 자세히 설명드리겠습니다.\n\n감사합니다.\nPortOne 팀`,
                personalizationScore: 8.0
            },
            {
                type: 'OPI - 호기심 유발형',
                product: 'One Payment Infra',
                subject: `${companyName}의 결제 시스템, 얼마나 효율적인가요?`,
                body: `${personalizedGreeting}\n\n${companyName}의 결제 시스템이 비즈니스 성장 속도를 따라가고 있나요?\n\nPG사 관리에 낭비되는 시간은 얼마나 될까요?\n\nPortOne으로 85% 리소스 절감과 15% 성공률 향상이 가능합니다.\n\n10분만 시간 내주실 수 있나요?\n\n감사합니다.\nPortOne 팀`,
                personalizationScore: 9.0
            },
            {
                type: '재무자동화 - 전문적 톤',
                product: '국내커머스채널 재무자동화 솔루션',
                subject: `${companyName}의 재무마감 자동화 제안`,
                body: `${personalizedGreeting}\n\n귀사의 다채널 커머스 운영에 깊은 인상을 받았습니다.\n\n현재 네이버스마트스토어, 카카오스타일, 카페24 등 채널별 재무마감에 월 수십 시간을 소비하고 계신가요? PortOne의 재무자동화 솔루션으로 90% 이상 단축하고 100% 데이터 정합성을 확보할 수 있습니다.\n\n브랜드별/채널별 매출보고서와 부가세신고자료까지 자동화로 제공해드립니다.\n\n감사합니다.\nPortOne 팀`,
                personalizationScore: 8.0
            },
            {
                type: '재무자동화 - 호기심 유발형',
                product: '국내커머스채널 재무자동화 솔루션',
                subject: `${companyName}의 재무팀, 얼마나 효율적인가요?`,
                body: `${personalizedGreeting}\n\n${companyName}의 재무팀이 네이버, 카카오, 카페24 등 채널별 데이터를 엑셀로 매번 매핑하는 데 얼마나 많은 시간을 쓰고 있나요? 구매확정내역과 정산내역이 매칭이 안 되어 고생하시지 않나요?\n\nPortOne의 재무자동화 솔루션으로 이 모든 문제를 해결할 수 있습니다. 90% 이상 시간 단축과 100% 데이터 정합성 보장이 가능합니다.\n\n15분만 시간 내주실 수 있나요?\n\n감사합니다.\nPortOne 팀`,
                personalizationScore: 9.0
            },
            {
                type: 'SaaS 스마트빌링 - 전문적 톤',
                product: '스마트빌링 솔루션',
                subject: `${companyName}의 구독 결제 시스템 혁신 제안`,
                body: `${personalizedGreeting}\n\n귀사의 SaaS 비즈니스에서 구독 결제 시스템으로 고민이 많으실 것 같습니다.\n\n현재 국내 PG의 구독 결제 한계와 Stripe 사용 시 발생하는 규제/환전 이슈로 어려움을 겪고 계시지 않으신가요?\n\nPortOne의 스마트빌링 솔루션으로:\n✅ 국내 구독 결제의 모든 한계 해결\n✅ Stripe 대안으로 규제 이슈 완전 회피\n✅ 던닝 관리 및 실패율 최소화 자동화\n✅ 구독 변경/취소 프로세스 완전 자동화\n\n안정적인 구독 비즈니스 운영을 위한 맞춤 컨설팅을 제공해드리겠습니다.\n\n감사합니다.\nPortOne 팀`,
                personalizationScore: 8.5
            },
            {
                type: '게임 웹상점 - 전문적 톤',
                product: '게임 웹상점 구축 서비스',
                subject: `${companyName}의 인앱결제 수수료 절감 솔루션`,
                body: `${personalizedGreeting}\n\n게임 업계의 30% 인앱결제 수수료 부담으로 고민이 많으실 것 같습니다.\n\n최근 많은 게임사들이 웹상점 구축을 통해 직접 판매를 고려하고 있지만, 구축과 운영의 복잡성 때문에 망설이고 계시지 않으신가요?\n\nPortOne의 게임 웹상점 구축 서비스로:\n🎮 게임 특화 PG 추천부터 구축까지 원스톱 제공\n💰 인앱결제 수수료 30% → 2-3%로 대폭 절감\n⚡ 실시간 결제 모니터링 및 게임 내 연동 지원\n🛡️ 게임 특성에 최적화된 보안 및 fraud 방지\n\n${companyName}의 매출 증대를 위한 웹상점 전략을 제안해드리겠습니다.\n\n감사합니다.\nPortOne 팀`,
                personalizationScore: 9.0
            }
        ];
    }
    
    // AI 기반 개인화 점수 계산
    calculateAIScore(research, emailContent) {
        let score = 5.0; // 기본 점수
        
        // 조사 정보가 있으면 점수 증가
        if (research && research.success && research.company_info) {
            score += 2.0;
            
            // 최신 뉴스나 트렌드 정보가 포함되어 있으면 추가 점수
            if (research.industry_trends) {
                score += 1.0;
            }
        }
        
        // 이메일 내용의 품질 평가
        if (emailContent) {
            const content = (emailContent.subject + ' ' + emailContent.body).toLowerCase();
            
            // PortOne 제품 관련 키워드 포함 시 점수 증가
            const productKeywords = ['결제', 'payment', 'portone', '원페이먼트', '인프라'];
            const hasProductKeywords = productKeywords.some(keyword => content.includes(keyword));
            if (hasProductKeywords) score += 1.0;
            
            // 개인화 요소 확인
            const personalizationKeywords = ['회사', '업계', '비즈니스', '맞춤'];
            const hasPersonalization = personalizationKeywords.some(keyword => content.includes(keyword));
            if (hasPersonalization) score += 0.5;
        }
        
        return Math.min(10, Math.max(1, Math.round(score * 10) / 10));
    }

    addBotMessage(message) {
        const chatContainer = document.getElementById('chatContainer');
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message bot-message';
        messageDiv.innerHTML = `<strong>PortOne 메일 봇</strong><br>${message.replace(/\n/g, '<br>')}`;
        chatContainer.appendChild(messageDiv);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    addUserMessage(message) {
        const chatContainer = document.getElementById('chatContainer');
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message user-message';
        // 줄바꿈을 <br> 태그로 변환하여 표시
        messageDiv.innerHTML = message.replace(/\n/g, '<br>');
        chatContainer.appendChild(messageDiv);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    sendMessage() {
        const userInput = document.getElementById('userInput');
        const message = userInput.value.trim();
        
        if (message) {
            this.addUserMessage(message);
            userInput.value = '';
            
            // 간단한 응답 로직
            setTimeout(() => {
                this.handleUserMessage(message);
            }, 500);
        }
    }

    async handleUserMessage(message) {
        // 개선 모드인지 확인
        if (this.isRefinementMode && this.currentRefinementTarget) {
            this.processRefinementRequest(message);
            return;
        }

        const lowerMessage = message.toLowerCase();
        
        console.log('🔍 메시지 분석 중:', lowerMessage); // 디버깅
        
        // 기본적으로 20자 이상이고 회사명이 있으면 재설득 메일로 간주
        const hasCompanyName = /[가-힣a-zA-Z]{2,}/.test(message);
        const isLongMessage = message.length > 20;
        
        // 재설득 메일 생성 요청 감지 (매우 넓게)
        const keywords = [
            '답장', '회신', '재설득', '반박', '대응',
            '했어', '했다', '라고', '왔어',
            '거절', '거부', '부정', '어렵', '불가',
            '써야', '써줘', '작성', '만들어', '생성', '보내',
            '비용', '부담', '시간', '없', 'pg', '변경', '예정',
            '검토', '비교', '미팅', '어떻게', '알려드립니다'
        ];
        
        const matchedKeywords = keywords.filter(k => lowerMessage.includes(k));
        console.log('✅ 매칭된 키워드:', matchedKeywords); // 디버깅
        
        const isReplyRequest = matchedKeywords.length > 0 || (hasCompanyName && isLongMessage);
        
        console.log('📊 판정 결과:', {
            isReplyRequest,
            matchedCount: matchedKeywords.length,
            hasCompanyName,
            isLongMessage,
            messageLength: message.length
        }); // 디버깅
        
        if (isReplyRequest) {
            this.addBotMessage('💬 재설득 메일 생성 요청을 확인했습니다. 회사명과 상황을 분석하고 있습니다...');
            console.log('🚀 재설득 메일 생성 시작'); // 디버깅
            await this.handleChatReply(message);
            return;
        }
        
        if (lowerMessage.includes('다시') || lowerMessage.includes('재생성')) {
            this.addBotMessage('새로운 메일 문안을 생성하려면 "메일 문안 생성하기" 버튼을 다시 클릭해주세요.');
        } else if (lowerMessage.includes('도움') || lowerMessage.includes('사용법')) {
            this.addBotMessage(`
📖 <strong>사용 방법 안내:</strong>

<strong>일반 메일 생성:</strong>
1. CSV 파일 업로드 (회사명, 이메일 등 포함)
2. "메일 문안 생성하기" 버튼 클릭
3. 생성된 문안 확인 및 복사

<strong>재설득 메일 생성 (새 기능!):</strong>
- 이 채팅창에 직접 입력하세요
- 예: "토스에서 비용이 부담된다고 했는데 재설득 메일 만들어줘"
- 예: "쿠팡 김철수 대표가 시간이 없다고 거절했어, 재설득 메일 부탁해"

💡 회사명과 상황만 알려주시면 자동으로 설득력 있는 재영업 메일을 만들어드립니다!
            `);
        } else {
            this.addBotMessage(`
💬 무엇을 도와드릴까요?

• <strong>재설득 메일이 필요하신가요?</strong>
  → "토스에서 비용이 부담된다고 했는데 재설득 메일 만들어줘"

• <strong>사용법이 궁금하신가요?</strong>
  → "도움말" 또는 "사용법" 입력

• <strong>일반 메일 생성은?</strong>
  → 왼쪽에 CSV 파일 업로드 후 버튼 클릭
            `);
        }
    }

    async processRefinementRequest(refinementRequest) {
        if (!refinementRequest.trim()) {
            this.addBotMessage('개선 요청사항을 입력해주세요.');
            return;
        }

        // URL 감지 로직
        const urlPattern = /https?:\/\/[^\s]+/g;
        const urls = refinementRequest.match(urlPattern);
        
        if (urls && urls.length > 0) {
            // 뉴스 기사 링크가 감지된 경우
            const newsUrl = urls[0]; // 첫 번째 URL 사용
            await this.processNewsAnalysisRequest(refinementRequest, newsUrl);
        } else {
            // 일반 개선 요청 처리
            await this.processGeneralRefinementRequest(refinementRequest);
        }
    }

    async processNewsAnalysisRequest(refinementRequest, newsUrl) {
        this.addBotMessage(`📰 뉴스 기사 링크를 감지했습니다: ${newsUrl}`);
        this.addBotMessage(`🔍 기사 내용을 분석하여 페인 포인트 기반 메일을 생성하고 있습니다...`);
        this.showLoading('뉴스 기사를 분석하고 있습니다...');
        
        try {
            // 현재 이메일 내용과 회사명 가져오기
            const { companyIndex, variationIndex } = this.currentRefinementTarget;
            const templateElement = document.getElementById(`ai_template_${companyIndex}_${variationIndex}`);
            const currentContent = templateElement ? templateElement.value : '';
            
            // 회사명 추출 (결과 데이터에서)
            let companyName = '';
            if (this.generatedResults && this.generatedResults[companyIndex]) {
                companyName = this.generatedResults[companyIndex].company['회사명'] || '';
            }
            
            console.log('뉴스 분석 요청 데이터:', {
                newsUrl,
                companyName,
                refinementRequest: refinementRequest.substring(0, 100) + '...'
            });
            
            // 뉴스 분석 API 호출
            const response = await fetch('/api/analyze-news', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    news_url: newsUrl,
                    company_name: companyName,
                    current_email: currentContent
                })
            });
            
            if (!response.ok) {
                const errorText = await response.text();
                console.error('뉴스 분석 API 오류:', response.status, errorText);
                throw new Error(`뉴스 분석 실패: ${response.status} - ${errorText}`);
            }
            
            const result = await response.json();
            console.log('뉴스 분석 결과:', result);
            
            if (result.success && result.analyzed_email) {
                // 뉴스 기반 분석 결과로 기존 문안 덮어쓰기
                this.displayNewsAnalysisResult(result, refinementRequest, newsUrl);
                
                // 성공 메시지 및 스크롤 버튼
                this.addBotMessage('✅ 뉴스 기사 분석을 통한 메일 문안 개선이 완료되었습니다!');
                this.addBotMessageWithScrollButton(
                    '📍 개선된 문안을 확인하시려면 아래 버튼을 클릭하세요.',
                    companyIndex,
                    variationIndex
                );
            } else {
                console.error('뉴스 분석 실패:', result);
                throw new Error(result.error || '뉴스 분석 처리 실패');
            }
            
        } catch (error) {
            console.error('뉴스 분석 오류:', error);
            this.addBotMessage('❌ 뉴스 기사 분석 중 오류가 발생했습니다: ' + error.message);
            this.addBotMessage('💡 일반 개선 요청으로 처리하겠습니다...');
            
            // 뉴스 분석 실패 시 일반 개선 요청으로 폴백
            await this.processGeneralRefinementRequest(refinementRequest);
        } finally {
            this.hideLoading();
            // 개선 모드 종료
            this.exitRefinementMode();
        }
    }

    async processGeneralRefinementRequest(refinementRequest) {
        this.addBotMessage(`🔄 "${refinementRequest}" 요청에 따라 이메일 문안을 개선하고 있습니다...`);
        this.showLoading('이메일 문안을 개선하고 있습니다...');
        
        try {
            // 현재 이메일 내용 가져오기
            const { companyIndex, variationIndex } = this.currentRefinementTarget;
            const templateElement = document.getElementById(`ai_template_${companyIndex}_${variationIndex}`);
            const currentContent = templateElement ? templateElement.value : '';
            
            console.log('개선 요청 데이터:', {
                companyIndex,
                variationIndex,
                currentContent: currentContent.substring(0, 100) + '...',
                refinementRequest
            });
            
            // 백엔드 API로 개선 요청
            // 회사 데이터도 함께 전송 (다시 작성 요청 시 필요)
            const companyData = this.generatedResults?.[companyIndex]?.company || {};
            
            const response = await fetch('/api/refine-email', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    current_email: currentContent,
                    refinement_request: refinementRequest,
                    company_data: companyData
                })
            });
            
            if (!response.ok) {
                const errorText = await response.text();
                console.error('API 응답 오류:', response.status, errorText);
                throw new Error(`API 오류: ${response.status} - ${errorText}`);
            }
            
            const result = await response.json();
            console.log('API 응답 결과:', result);
            
            if (result.success && result.regenerated) {
                // "다시 작성" 요청으로 전체 문안이 재생성된 경우
                this.addBotMessage('✅ 전체 문안을 다시 생성했습니다!');
                
                // 기존 회사 데이터 가져오기
                const companyData = this.generatedResults[companyIndex]?.company || {};
                
                // 재생성된 variations로 결과 업데이트
                const regeneratedResult = {
                    company: companyData,
                    emails: {
                        variations: result.variations || {},
                        recommended: result.recommended || {}
                    }
                };
                
                // generatedResults 업데이트
                if (this.generatedResults && this.generatedResults[companyIndex]) {
                    this.generatedResults[companyIndex] = regeneratedResult;
                }
                
                // 전체 결과 다시 표시
                this.displayAIGeneratedTemplates(this.generatedResults);
                
                this.addBotMessage('📍 새로 생성된 문안을 위에서 확인하세요!');
                
                // 맨 위로 스크롤
                window.scrollTo({ top: 0, behavior: 'smooth' });
                
            } else if (result.success && result.refined_email) {
                // 일반 개선 요청
                // 개선된 내용으로 기존 문안 덮어쓰기
                this.updateExistingVariation(companyIndex, variationIndex, result.refined_email, refinementRequest);
                
                // 스크롤 이동 버튼이 포함된 메시지 추가
                this.addBotMessage('✅ 이메일 문안 개선이 완료되었습니다!');
                this.addBotMessageWithScrollButton(
                    '📍 개선된 문안을 확인하시려면 아래 버튼을 클릭하세요.',
                    companyIndex,
                    variationIndex
                );
            } else {
                console.error('개선 실패:', result);
                throw new Error(result.error || '개선 요청 처리 실패');
            }
            
        } catch (error) {
            console.error('개선 요청 오류:', error);
            this.addBotMessage('❌ 이메일 개선 중 오류가 발생했습니다: ' + error.message);
        } finally {
            this.hideLoading();
            // 개선 모드 종료
            this.exitRefinementMode();
        }
    }

    enterRefinementMode(companyIndex, variationIndex) {
        this.isRefinementMode = true;
        this.currentRefinementTarget = { companyIndex, variationIndex };
        
        const userInput = document.getElementById('userInput');
        const sendBtn = document.getElementById('sendBtn');
        
        userInput.disabled = false;
        userInput.placeholder = '개선 요청사항을 상세히 입력하세요 (예: "제목을 더 임팩트있게 바꾸고, 본문은 친근한 톤으로 작성해주세요. 기술적인 수치보다는 비즈니스 가치에 집중해서 써주세요")';
        userInput.focus();
        sendBtn.disabled = false;
        
        this.addBotMessage(`💡 위 텍스트박스에 개선 요청사항을 상세히 입력하고 전송 버튼을 눌러주세요!

📝 **일반 개선 요청:**
• "제목을 더 임팩트있게 바꿔주세요"
• "본문 톤을 친근하게 바꾸고 기술적 수치는 줄여주세요"
• "인사말을 더 격식있게 하고 결론 부분을 강하게 마무리해주세요"
• "전체적으로 더 짧게 요약하되 핵심 가치는 유지해주세요"

🎨 **외적 형식 요청:**
• "핵심 내용을 볼드체로 강조해주세요"
• "혜택 부분을 불릿 포인트로 만들어주세요"
• "CTA 부분을 버튼 스타일로 해주세요"
• "중요한 수치는 큰 글씨로 표시해주세요"

🆕 **뉴스 기사 링크 분석 (NEW!):**
• 뉴스 기사 URL을 포함하여 입력하면 자동으로 기사를 분석합니다
• 기사 내용에서 페인 포인트를 도출하여 맞춤형 메일을 생성합니다
• 예: "https://news.example.com/article 이 기사를 바탕으로 메일을 작성해주세요"
• 업계 트렌드와 이슈를 반영한 더욱 설득력 있는 메일 문안을 제공합니다`);
    }

    exitRefinementMode() {
        this.isRefinementMode = false;
        this.currentRefinementTarget = null;
        
        const userInput = document.getElementById('userInput');
        const sendBtn = document.getElementById('sendBtn');
        
        userInput.value = '';
        userInput.placeholder = '추가 요청사항이나 질문을 입력하세요... (개선 요청은 각 메일의 "개선 요청" 버튼 클릭)';
        
        // 이메일 생성이 완료되었으면 계속 활성화 유지
        if (this.uploadedData && this.uploadedData.length > 0) {
            userInput.disabled = false;
            sendBtn.disabled = false;
        } else {
            userInput.disabled = true;
            sendBtn.disabled = true;
        }
    }

    enableUserInput() {
        const userInput = document.getElementById('userInput');
        const sendBtn = document.getElementById('sendBtn');
        
        userInput.disabled = false;
        sendBtn.disabled = false;
        userInput.placeholder = '추가 요청사항이나 질문을 입력하세요... (개선 요청은 각 메일의 "개선 요청" 버튼 클릭)';
        
        this.addBotMessage('💡 이제 추가 질문이나 요청사항을 위 텍스트박스에 입력할 수 있습니다!');
    }
    
    // 스크롤 버튼이 포함된 챗봇 메시지 추가
    addBotMessageWithScrollButton(message, companyIndex, variationIndex) {
        const chatContainer = document.getElementById('chatContainer');
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message bot-message';
        messageDiv.innerHTML = `
            <strong>PortOne 메일 봇</strong><br>
            ${message}<br><br>
            <button class="btn btn-sm btn-success" onclick="window.emailChatbot.scrollToVariation(${companyIndex}, ${variationIndex})">
                <i class="fas fa-arrow-down"></i> 개선된 문안으로 이동
            </button>
        `;
        chatContainer.appendChild(messageDiv);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    clearChat() {
        const chatContainer = document.getElementById('chatContainer');
        chatContainer.innerHTML = `
            <div class="message bot-message">
                <strong>PortOne 메일 봇</strong><br>
                대화가 초기화되었습니다. 새로운 메일 문안 생성을 시작해보세요! 👋
            </div>
        `;
    }

    // 자동 저장: 세션을 localStorage에 저장
    autoSaveSession(results) {
        // 세션 불러오기 중이면 자동 저장 스킵
        if (this.isLoadingSession) {
            console.log('⏭️ 세션 불러오기 중이므로 자동 저장 스킵');
            return;
        }
        
        try {
            const timestamp = new Date().toISOString();
            const sessionData = {
                timestamp: timestamp,
                date: new Date().toLocaleString('ko-KR'),
                results: results,
                uploadedData: this.uploadedData,
                companyCount: results.length
            };
            
            // 세션 ID 생성 (타임스탬프 기반)
            const sessionId = `session_${Date.now()}`;
            
            // 개별 세션 저장
            localStorage.setItem(sessionId, JSON.stringify(sessionData));
            
            // 세션 목록에 추가
            let sessionList = JSON.parse(localStorage.getItem('sessionList') || '[]');
            sessionList.unshift({
                id: sessionId,
                date: sessionData.date,
                companyCount: sessionData.companyCount,
                timestamp: timestamp
            });
            
            // 최근 20개 세션만 유지
            if (sessionList.length > 20) {
                const oldSessions = sessionList.slice(20);
                oldSessions.forEach(session => {
                    localStorage.removeItem(session.id);
                });
                sessionList = sessionList.slice(0, 20);
            }
            
            localStorage.setItem('sessionList', JSON.stringify(sessionList));
            
            console.log('✅ 세션 자동 저장 완료:', sessionId);
            this.showSaveNotification('💾 자동 저장 완료!');
            
            // 세션 목록 UI 업데이트
            this.updateSessionListUI();
            
        } catch (error) {
            console.error('세션 저장 오류:', error);
            this.addBotMessage('⚠️ 세션 저장에 실패했습니다. 브라우저 저장 공간을 확인해주세요.');
        }
    }
    
    // 세션 불러오기
    loadSession(sessionId) {
        try {
            const sessionData = JSON.parse(localStorage.getItem(sessionId));
            if (!sessionData) {
                alert('세션을 찾을 수 없습니다.');
                return;
            }
            
            // 데이터 복원
            this.uploadedData = sessionData.uploadedData || [];
            this.generatedResults = sessionData.results;
            
            // 불러오기 모드 플래그 설정 (자동 저장 방지)
            this.isLoadingSession = true;
            
            // UI 업데이트
            this.displayAIGeneratedTemplates(sessionData.results);
            
            // 플래그 해제
            this.isLoadingSession = false;
            
            this.addBotMessage(`✅ 세션을 불러왔습니다!\n생성일: ${sessionData.date}\n회사 수: ${sessionData.companyCount}개`);
            
            console.log('✅ 세션 불러오기 완료:', sessionId);
            
        } catch (error) {
            console.error('세션 불러오기 오류:', error);
            alert('세션 불러오기에 실패했습니다.');
        }
    }
    
    // 세션 삭제
    deleteSession(sessionId) {
        if (!confirm('이 세션을 삭제하시겠습니까?')) {
            return;
        }
        
        try {
            // 세션 데이터 삭제
            localStorage.removeItem(sessionId);
            
            // 세션 목록에서 제거
            let sessionList = JSON.parse(localStorage.getItem('sessionList') || '[]');
            sessionList = sessionList.filter(session => session.id !== sessionId);
            localStorage.setItem('sessionList', JSON.stringify(sessionList));
            
            // UI 업데이트
            this.updateSessionListUI();
            
            console.log('✅ 세션 삭제 완료:', sessionId);
            
        } catch (error) {
            console.error('세션 삭제 오류:', error);
            alert('세션 삭제에 실패했습니다.');
        }
    }
    
    // 세션 목록 UI 업데이트
    updateSessionListUI() {
        const sessionList = JSON.parse(localStorage.getItem('sessionList') || '[]');
        const sessionListContainer = document.getElementById('sessionListContainer');
        
        if (!sessionListContainer) return;
        
        if (sessionList.length === 0) {
            sessionListContainer.innerHTML = '<p class="text-muted small">저장된 세션이 없습니다.</p>';
            return;
        }
        
        sessionListContainer.innerHTML = sessionList.map(session => `
            <div class="session-item d-flex justify-content-between align-items-center mb-2 p-2 border rounded">
                <div>
                    <small class="d-block"><strong>${session.date}</strong></small>
                    <small class="text-muted">${session.companyCount}개 회사</small>
                </div>
                <div class="btn-group btn-group-sm">
                    <button class="btn btn-outline-primary" onclick="window.emailChatbot.loadSession('${session.id}')">
                        <i class="fas fa-folder-open"></i> 불러오기
                    </button>
                    <button class="btn btn-outline-danger" onclick="window.emailChatbot.deleteSession('${session.id}')">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
        `).join('');
    }
    
    // 저장 알림 표시
    showSaveNotification(message) {
        const notification = document.createElement('div');
        notification.className = 'alert alert-success position-fixed';
        notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; animation: fadeIn 0.3s;';
        notification.innerHTML = `<i class="fas fa-check-circle"></i> ${message}`;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.style.animation = 'fadeOut 0.3s';
            setTimeout(() => {
                document.body.removeChild(notification);
            }, 300);
        }, 2000);
    }

    showLoading(show) {
        const indicator = document.getElementById('loadingIndicator');
        if (!indicator) return;
        
        if (typeof show === 'string') {
            // 메시지 문자열이 전달된 경우
            indicator.style.display = 'block';
            const messageElement = indicator.querySelector('.loading-message');
            if (messageElement) {
                messageElement.textContent = show;
            }
        } else {
            // boolean이 전달된 경우
            indicator.style.display = show ? 'block' : 'none';
        }
    }

    hideLoading() {
        const indicator = document.getElementById('loadingIndicator');
        if (indicator) {
            indicator.style.display = 'none';
        }
    }

    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    // 전역 접근을 위한 인스턴스 저장
    static getInstance() {
        if (!window.emailChatbot) {
            window.emailChatbot = new EmailCopywritingChatbot();
        }
        return window.emailChatbot;
    }
}

// 클립보드 복사 함수
function copyToClipboard(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.select();
        element.setSelectionRange(0, 99999);
        document.execCommand('copy');
        
        // 성공 메시지 표시
        const button = document.querySelector(`button[onclick="copyToClipboard('${elementId}')"]`);
        if (button) {
            const originalText = button.innerHTML;
            button.innerHTML = '<i class="fas fa-check"></i> 복사됨!';
            button.classList.add('btn-success');
            button.classList.remove('btn-outline-primary');
            
            setTimeout(() => {
                button.innerHTML = originalText;
                button.classList.remove('btn-success');
                button.classList.add('btn-outline-primary');
            }, 2000);
        }
    }
}

// 이메일 문안 개선 요청 함수
async function refineEmailCopy(companyIndex, variationIndex) {
    const chatbot = window.emailChatbot;
    if (!chatbot) return;
    
    // 개선 모드로 전환
    chatbot.enterRefinementMode(companyIndex, variationIndex);
}

// 제목만 복사하는 함수
function copySubjectToClipboard(subject) {
    // 최신 브라우저의 Clipboard API 사용
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(subject).then(() => {
            showCopySuccess('📋 제목이 클립보드에 복사되었습니다!');
        }).catch(err => {
            console.error('복사 실패:', err);
            fallbackCopyTextToClipboard(subject);
        });
    } else {
        // 폴백 방법
        fallbackCopyTextToClipboard(subject);
    }
}

// 텍스트 복사 함수 (개선된 버전) - 본문만 복사 (서식 포함)
function copyTextToClipboard(subject, body) {
    // body가 마크다운 형식이면 HTML로 변환
    let bodyHtml = body;
    if (typeof body === 'string' && !body.trim().startsWith('<')) {
        // 마크다운 형식인 경우 HTML로 변환
        bodyHtml = convertMarkdownToHtml(body);
    }
    
    // 최신 Clipboard API 사용 (HTML 형식 복사 지원)
    if (navigator.clipboard && window.ClipboardItem) {
        try {
            // HTML과 Plain Text 모두 제공
            const htmlBlob = new Blob([bodyHtml], { type: 'text/html' });
            const plainText = bodyHtml
                .replace(/<br\s*\/?>/gi, '\n')
                .replace(/<\/p>/gi, '\n\n')
                .replace(/<p[^>]*>/gi, '')
                .replace(/<[^>]+>/g, '')
                .replace(/&nbsp;/g, ' ')
                .replace(/&lt;/g, '<')
                .replace(/&gt;/g, '>')
                .replace(/&amp;/g, '&')
                .trim();
            const textBlob = new Blob([plainText], { type: 'text/plain' });
            
            const clipboardItem = new ClipboardItem({
                'text/html': htmlBlob,
                'text/plain': textBlob
            });
            
            navigator.clipboard.write([clipboardItem]).then(() => {
                showCopySuccess('📋 본문이 서식과 함께 클립보드에 복사되었습니다!');
            }).catch(err => {
                console.error('ClipboardItem 복사 실패:', err);
                fallbackCopyWithContentEditable(bodyHtml);
            });
            return;
        } catch (err) {
            console.error('ClipboardItem 생성 실패:', err);
        }
    }
    
    // 폴백: contentEditable 방식
    fallbackCopyWithContentEditable(bodyHtml);
}

// contentEditable을 사용한 폴백 복사
function fallbackCopyWithContentEditable(body) {
    const tempDiv = document.createElement('div');
    tempDiv.contentEditable = true;
    tempDiv.style.position = 'fixed';
    tempDiv.style.left = '-9999px';
    tempDiv.style.opacity = '0';
    
    // HTML을 설정
    tempDiv.innerHTML = body;
    document.body.appendChild(tempDiv);
    
    try {
        // 전체 선택
        const range = document.createRange();
        range.selectNodeContents(tempDiv);
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
        
        // 복사 실행
        const successful = document.execCommand('copy');
        
        if (successful) {
            showCopySuccess('📋 본문이 서식과 함께 클립보드에 복사되었습니다!');
        } else {
            throw new Error('execCommand 실패');
        }
        
        // 선택 해제
        selection.removeAllRanges();
    } catch (err) {
        console.error('서식 복사 실패:', err);
        alert('복사에 실패했습니다. 수동으로 복사해주세요.');
    } finally {
        document.body.removeChild(tempDiv);
    }
}

// HTML을 순수 텍스트로 변환하는 개선된 함수 (폴백용 - 사용 안 함)
function htmlToPlainText(html) {
    if (!html) return '';
    
    // HTML 태그 제거 및 특수 문자 변환 (더 정교한 처리)
    let text = html
        // 먼저 블록 레벨 태그들을 줄바꿈으로 변환
        .replace(/<\/?(div|p|h[1-6]|li|tr|td|th|section|article|header|footer|nav|aside|main)[^>]*>/gi, '\n')
        .replace(/<br\s*\/?>/gi, '\n')           // <br> 태그를 줄바꿈으로
        .replace(/<\/li>/gi, '\n')               // </li> 태그를 줄바꿈으로
        .replace(/<li[^>]*>/gi, '• ')            // <li> 태그를 불릿으로
        .replace(/<\/ol>/gi, '\n')               // </ol> 태그를 줄바꿈으로
        .replace(/<\/ul>/gi, '\n')               // </ul> 태그를 줄바꿈으로
        .replace(/<strong[^>]*>(.*?)<\/strong>/gi, '$1')  // <strong> 태그 내용만 유지
        .replace(/<b[^>]*>(.*?)<\/b>/gi, '$1')            // <b> 태그 내용만 유지
        .replace(/<em[^>]*>(.*?)<\/em>/gi, '$1')          // <em> 태그 내용만 유지
        .replace(/<i[^>]*>(.*?)<\/i>/gi, '$1')            // <i> 태그 내용만 유지
        .replace(/<a[^>]*>(.*?)<\/a>/gi, '$1')            // <a> 태그 내용만 유지
        .replace(/<[^>]*>/g, '')                          // 모든 HTML 태그 제거
        .replace(/&nbsp;/g, ' ')                          // &nbsp;를 공백으로
        .replace(/&lt;/g, '<')                            // &lt;를 <로
        .replace(/&gt;/g, '>')                            // &gt;를 >로
        .replace(/&amp;/g, '&')                           // &amp;를 &로
        .replace(/&quot;/g, '"')                          // &quot;를 "로
        .replace(/&#39;/g, "'")                           // &#39;를 '로
        .replace(/&hellip;/g, '...')                      // &hellip;를 ...로
        .replace(/&mdash;/g, '—')                         // &mdash;를 —로
        .replace(/&ndash;/g, '–')                         // &ndash;를 –로
        .replace(/\n\s*\n\s*\n/g, '\n\n')                // 3개 이상 연속 줄바꿈을 2개로 제한
        .replace(/^\s+|\s+$/g, '')                        // 앞뒤 공백 제거
        .replace(/[ \t]+/g, ' ')                          // 연속된 공백을 하나로
        .trim();                                          // 최종 trim
        
    return text;
}

// 폴백 복사 함수
function fallbackCopyTextToClipboard(text) {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.left = '-999999px';
    textArea.style.top = '-999999px';
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    
    try {
        document.execCommand('copy');
        showCopySuccess('📋 본문이 클립보드에 복사되었습니다!');
    } catch (err) {
        console.error('폴백 복사 실패:', err);
        alert('복사에 실패했습니다. 수동으로 복사해주세요.');
    } finally {
        document.body.removeChild(textArea);
    }
}

// HTML 템플릿 변환 함수
function convertToHtmlTemplate(subject, body, companyIndex, variationIndex) {
    const htmlTemplate = generateHtmlEmailTemplate(subject, body);
    
    // 모달 창으로 HTML 템플릿 표시
    showHtmlTemplateModal(htmlTemplate, subject);
}

// HTML 이메일 템플릿 생성
function generateHtmlEmailTemplate(subject, body) {
    // 본문을 HTML로 변환 (줄바꿈을 <br>로, 강조 표시 등)
    let htmlBody = body
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/•/g, '&bull;');
    
    // 이메일 주소나 전화번호 링크 변환
    htmlBody = htmlBody
        .replace(/(\w+@\w+\.\w+)/g, '<a href="mailto:$1">$1</a>')
        .replace(/(\d{2,3}-\d{3,4}-\d{4})/g, '<a href="tel:$1">$1</a>');
    
    return `<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>${subject}</title>
    <style>
        body {
            font-family: 'Malgun Gothic', '맑은 고딕', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f9f9f9;
        }
        .email-container {
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .header {
            border-bottom: 2px solid #007bff;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }
        .logo {
            font-size: 24px;
            font-weight: bold;
            color: #007bff;
            margin-bottom: 10px;
        }
        .content {
            font-size: 16px;
            line-height: 1.8;
        }
        .content p {
            margin-bottom: 15px;
        }
        .highlight {
            background-color: #e3f2fd;
            padding: 15px;
            border-left: 4px solid #007bff;
            margin: 20px 0;
        }
        .cta-button {
            display: inline-block;
            background-color: #007bff;
            color: white;
            padding: 12px 25px;
            text-decoration: none;
            border-radius: 5px;
            font-weight: bold;
            margin: 20px 0;
        }
        .footer {
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #eee;
            font-size: 14px;
            color: #666;
        }
        .signature {
            margin-top: 30px;
            padding: 15px;
            background-color: #f8f9fa;
            border-radius: 5px;
        }
    </style>
</head>
<body>
    <div class="email-container">
        <div class="header">
            <div class="logo">PortOne</div>
            <div style="color: #666; font-size: 14px;">One Payment Infra</div>
        </div>
        
        <div class="content">
            <p>${htmlBody}</p>
        </div>
        
        <div class="signature">
            <strong>PortOne 팀</strong><br>
            <span style="color: #666;">One Payment Infra 전문가</span><br>
            <a href="mailto:contact@portone.io">contact@portone.io</a><br>
            <a href="https://portone.io">https://portone.io</a>
        </div>
        
        <div class="footer">
            <p style="font-size: 12px; color: #999;">
                이 이메일은 PortOne의 One Payment Infra 제품 소개를 위해 발송되었습니다.<br>
                더 이상 이메일 수신을 원하지 않으시면 <a href="#">여기</a>를 클릭해주세요.
            </p>
        </div>
    </div>
</body>
</html>`;
}

// HTML 템플릿 모달 표시
function showHtmlTemplateModal(htmlTemplate, subject) {
    // 기존 모달이 있으면 제거
    const existingModal = document.getElementById('htmlTemplateModal');
    if (existingModal) {
        existingModal.remove();
    }
    
    // 모달 HTML 생성
    const modalHtml = `
        <div class="modal fade" id="htmlTemplateModal" tabindex="-1" aria-hidden="true">
            <div class="modal-dialog modal-xl">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">
                            <i class="fas fa-code"></i> HTML 이메일 템플릿
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="row">
                            <div class="col-md-6">
                                <h6><i class="fas fa-eye"></i> 미리보기</h6>
                                <div class="border p-3" style="height: 400px; overflow-y: auto;">
                                    <iframe id="htmlPreview" style="width: 100%; height: 100%; border: none;"></iframe>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <h6><i class="fas fa-code"></i> HTML 코드</h6>
                                <textarea id="htmlCode" class="form-control" style="height: 400px; font-family: monospace; font-size: 12px;">${htmlTemplate.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</textarea>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-outline-primary" onclick="copyHtmlToClipboard()">
                            <i class="fas fa-copy"></i> HTML 코드 복사
                        </button>
                        <button type="button" class="btn btn-outline-success" onclick="downloadHtmlFile('${subject}')">
                            <i class="fas fa-download"></i> HTML 파일 다운로드
                        </button>
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">닫기</button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // 모달을 body에 추가
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    
    // 모달 표시
    const modal = new bootstrap.Modal(document.getElementById('htmlTemplateModal'));
    modal.show();
    
    // 미리보기 iframe에 HTML 로드
    setTimeout(() => {
        const iframe = document.getElementById('htmlPreview');
        const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
        iframeDoc.open();
        iframeDoc.write(htmlTemplate);
        iframeDoc.close();
    }, 100);
}

// HTML 코드 복사
function copyHtmlToClipboard() {
    const htmlCode = document.getElementById('htmlCode').value;
    
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(htmlCode).then(() => {
            showCopySuccess('HTML 코드가 클립보드에 복사되었습니다!');
        }).catch(err => {
            console.error('복사 실패:', err);
        });
    } else {
        // 폴백 방법
        const textArea = document.getElementById('htmlCode');
        textArea.select();
        document.execCommand('copy');
        showCopySuccess('HTML 코드가 클립보드에 복사되었습니다!');
    }
}

// HTML 파일 다운로드
function downloadHtmlFile(subject) {
    const htmlCode = document.getElementById('htmlCode').value;
    const blob = new Blob([htmlCode], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = `${subject.replace(/[^a-zA-Z0-9가-힣]/g, '_')}_email_template.html`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    showCopySuccess('HTML 파일이 다운로드되었습니다!');
}

// 뉴스 기반 이메일 복사 함수
function copyNewsEmailToClipboard(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        const emailContent = element.value;
        const plainTextContent = htmlToPlainText(emailContent);
        
        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(plainTextContent).then(() => {
                showCopySuccess('📰 뉴스 기반 메일 문안이 텍스트로 복사되었습니다!');
            }).catch(err => {
                console.error('복사 실패:', err);
                fallbackCopyTextToClipboard(plainTextContent);
            });
        } else {
            fallbackCopyTextToClipboard(plainTextContent);
        }
    }
}

// 개선된 이메일 복사 함수
function copyRefinedEmailToClipboard(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        const emailContent = element.value;
        const plainTextContent = htmlToPlainText(emailContent);
        
        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(plainTextContent).then(() => {
                showCopySuccess('✨ 개선된 메일 문안이 텍스트로 복사되었습니다!');
            }).catch(err => {
                console.error('복사 실패:', err);
                fallbackCopyTextToClipboard(plainTextContent);
            });
        } else {
            fallbackCopyTextToClipboard(plainTextContent);
        }
    }
}

// 복사 성공 메시지 표시
function showCopySuccess(message) {
    // 토스트 메시지 생성
    const toast = document.createElement('div');
    toast.className = 'toast align-items-center text-white bg-success border-0';
    toast.style.position = 'fixed';
    toast.style.top = '20px';
    toast.style.right = '20px';
    toast.style.zIndex = '9999';
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                <i class="fas fa-check-circle me-2"></i>${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    
    document.body.appendChild(toast);
    
    // Bootstrap 토스트 초기화 및 표시
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
    
    // 토스트가 숨겨진 후 DOM에서 제거
    toast.addEventListener('hidden.bs.toast', () => {
        document.body.removeChild(toast);
    });
}

// 범용 토스트 메시지 표시 함수
function showToast(message, type = 'success') {
    // 타입별 색상 및 아이콘 설정
    const typeConfig = {
        'success': { bg: 'bg-success', icon: 'fa-check-circle' },
        'danger': { bg: 'bg-danger', icon: 'fa-exclamation-circle' },
        'error': { bg: 'bg-danger', icon: 'fa-exclamation-circle' },
        'info': { bg: 'bg-info', icon: 'fa-info-circle' },
        'warning': { bg: 'bg-warning', icon: 'fa-exclamation-triangle' }
    };
    
    const config = typeConfig[type] || typeConfig['success'];
    
    // 토스트 메시지 생성
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white ${config.bg} border-0`;
    toast.style.position = 'fixed';
    toast.style.top = '20px';
    toast.style.right = '20px';
    toast.style.zIndex = '9999';
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                <i class="fas ${config.icon} me-2"></i>${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    
    document.body.appendChild(toast);
    
    // Bootstrap 토스트 초기화 및 표시
    const bsToast = new bootstrap.Toast(toast, {
        autohide: true,
        delay: 3000
    });
    bsToast.show();
    
    // 토스트가 숨겨진 후 DOM에서 제거
    toast.addEventListener('hidden.bs.toast', () => {
        document.body.removeChild(toast);
    });
}

// 조사 내용 전체 보기/접기 토글 함수
function toggleResearchContent(button) {
    const contentDiv = button.previousElementSibling;
    const icon = button.querySelector('i');
    const text = button.lastChild;
    
    if (contentDiv.style.maxHeight === '300px' || !contentDiv.style.maxHeight) {
        contentDiv.style.maxHeight = 'none';
        icon.className = 'fas fa-compress-alt';
        text.textContent = ' 접기';
    } else {
        contentDiv.style.maxHeight = '300px';
        icon.className = 'fas fa-expand-alt';
        text.textContent = ' 전체 내용 보기';
    }
}

// 이메일 주소 클립보드 복사 함수
function copyToClipboard(text) {
    if (navigator.clipboard && window.isSecureContext) {
        // 최신 브라우저에서 Clipboard API 사용
        navigator.clipboard.writeText(text).then(() => {
            showCopySuccess('📧 이메일 주소가 클립보드에 복사되었습니다!');
        }).catch(err => {
            console.error('클립보드 복사 실패:', err);
            fallbackCopyEmailToClipboard(text);
        });
    } else {
        // 구형 브라우저 지원
        fallbackCopyEmailToClipboard(text);
    }
}

// 구형 브라우저용 이메일 클립보드 복사 함수
function fallbackCopyEmailToClipboard(text) {
    const textArea = document.createElement("textarea");
    textArea.value = text;
    
    // 화면에 보이지 않게 설정
    textArea.style.top = "0";
    textArea.style.left = "0";
    textArea.style.position = "fixed";
    textArea.style.opacity = "0";
    
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    
    try {
        const successful = document.execCommand('copy');
        if (successful) {
            showCopySuccess('📧 이메일 주소가 클립보드에 복사되었습니다!');
        } else {
            alert('클립보드 복사에 실패했습니다.');
        }
    } catch (err) {
        console.error('클립보드 복사 실패:', err);
        alert('클립보드 복사에 실패했습니다.');
    }
    
    document.body.removeChild(textArea);
}

// 사이드바 토글 함수
function toggleSidebar() {
    const sidebar = document.getElementById('emailSidebar');
    const overlay = document.getElementById('sidebarOverlay');
    sidebar.classList.toggle('active');
    overlay.classList.toggle('active');
}

// 이메일 문안 저장 함수
function saveEmailDraft(companyName, variationType, subject, body) {
    try {
        // localStorage에서 저장된 문안 가져오기
        let savedDrafts = JSON.parse(localStorage.getItem('savedEmailDrafts') || '[]');
        
        // 새 문안 추가
        const newDraft = {
            id: Date.now(),
            companyName: companyName,
            variationType: variationType,
            subject: subject,
            body: body.replace(/\\n/g, '\n'), // 줄바꿈 복원
            savedAt: new Date().toISOString()
        };
        
        savedDrafts.unshift(newDraft); // 최신순으로 추가
        
        // 최대 100개까지만 저장
        if (savedDrafts.length > 100) {
            savedDrafts = savedDrafts.slice(0, 100);
        }
        
        // localStorage에 저장
        localStorage.setItem('savedEmailDrafts', JSON.stringify(savedDrafts));
        
        // 사이드바 업데이트
        loadSavedDrafts();
        
        // 성공 메시지
        showToast('✅ 메일 문안이 저장되었습니다!', 'success');
        
    } catch (error) {
        console.error('저장 실패:', error);
        showToast('❌ 저장에 실패했습니다.', 'error');
    }
}

// 저장된 문안 로드 및 표시
function loadSavedDrafts() {
    const savedDrafts = JSON.parse(localStorage.getItem('savedEmailDrafts') || '[]');
    const savedCompanies = JSON.parse(localStorage.getItem('savedCompanyDrafts') || '[]');
    const container = document.getElementById('savedEmailsList');
    
    if (savedDrafts.length === 0 && savedCompanies.length === 0) {
        container.innerHTML = '<p class="text-muted text-center">저장된 문안이 없습니다.</p>';
        return;
    }
    
    let html = '';
    
    // 회사별 전체 저장 표시
    if (savedCompanies.length > 0) {
        html += '<h6 class="text-primary mb-3"><i class="fas fa-building"></i> 회사별 전체 저장</h6>';
        
        savedCompanies.forEach((company) => {
            const savedDate = new Date(company.savedAt);
            const dateStr = savedDate.toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' });
            const timeStr = savedDate.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });
            
            html += `
                <div class="saved-email-item" style="border-left: 3px solid #28a745;">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <div>
                            <strong><i class="fas fa-building text-success"></i> ${company.companyName}</strong>
                            <br><small class="text-muted">${company.variations.length}개 문안</small>
                        </div>
                        <button class="btn btn-sm btn-outline-danger" onclick="deleteCompanyDraft(${company.id})" title="삭제">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                    <div class="small text-muted mb-2">
                        <i class="fas fa-clock"></i> ${dateStr} ${timeStr}
                    </div>
                    <div class="small mb-2">
                        ${company.variations.map(v => `<span class="badge bg-secondary me-1">${v.type}</span>`).join('')}
                    </div>
                    <div class="d-flex gap-2 flex-wrap">
                        <button class="btn btn-sm btn-success" onclick="loadCompanyToMain(${company.id})" title="메인 화면에 전체 불러오기">
                            <i class="fas fa-arrow-right"></i> 전체 불러오기
                        </button>
                        <button class="btn btn-sm btn-info" onclick="viewCompanyDetails(${company.id})" title="상세보기">
                            <i class="fas fa-eye"></i> 상세보기
                        </button>
                    </div>
                </div>
            `;
        });
    }
    
    // 개별 문안 저장 표시
    if (savedDrafts.length > 0) {
        html += '<h6 class="text-primary mb-3 mt-4"><i class="fas fa-file-alt"></i> 개별 문안 저장</h6>';
        
        savedDrafts.forEach((draft) => {
            const savedDate = new Date(draft.savedAt);
            const dateStr = savedDate.toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' });
            const timeStr = savedDate.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });
            
            html += `
                <div class="saved-email-item">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <div>
                            <strong>${draft.companyName}</strong>
                            <br><small class="text-muted">${draft.variationType}</small>
                        </div>
                        <button class="btn btn-sm btn-outline-danger" onclick="deleteDraft(${draft.id})" title="삭제">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                    <div class="small text-muted mb-2">
                        <i class="fas fa-clock"></i> ${dateStr} ${timeStr}
                    </div>
                    <div class="small mb-2" style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                        <strong>제목:</strong> ${draft.subject}
                    </div>
                    <div class="d-flex gap-2 flex-wrap">
                        <button class="btn btn-sm btn-success" onclick="loadDraftToMain(${draft.id})" title="메인 화면으로 불러와서 개선 요청 기능 사용">
                            <i class="fas fa-arrow-right"></i> 불러오기
                        </button>
                        <button class="btn btn-sm btn-primary" onclick="copyDraftSubject(${draft.id})" title="제목만 복사">
                            <i class="fas fa-copy"></i> 제목
                        </button>
                        <button class="btn btn-sm btn-primary" onclick="copyFullDraft(${draft.id})" title="제목+본문 전체 복사">
                            <i class="fas fa-copy"></i> 전체
                        </button>
                        <button class="btn btn-sm btn-warning" onclick="editDraft(${draft.id})" title="직접 수정">
                            <i class="fas fa-edit"></i> 수정
                        </button>
                    </div>
                </div>
            `;
        });
    }
    
    container.innerHTML = html;
}

// 저장된 문안 삭제
function deleteDraft(draftId) {
    if (!confirm('이 문안을 삭제하시겠습니까?')) {
        return;
    }
    
    let savedDrafts = JSON.parse(localStorage.getItem('savedEmailDrafts') || '[]');
    savedDrafts = savedDrafts.filter(draft => draft.id !== draftId);
    localStorage.setItem('savedEmailDrafts', JSON.stringify(savedDrafts));
    loadSavedDrafts();
    showToast('문안이 삭제되었습니다.', 'info');
}

// 회사별 저장 데이터 삭제
function deleteCompanyDraft(companyId) {
    if (!confirm('이 회사의 모든 문안을 삭제하시겠습니까?')) {
        return;
    }
    
    let savedCompanies = JSON.parse(localStorage.getItem('savedCompanyDrafts') || '[]');
    savedCompanies = savedCompanies.filter(company => company.id !== companyId);
    localStorage.setItem('savedCompanyDrafts', JSON.stringify(savedCompanies));
    loadSavedDrafts();
    showToast('회사 데이터가 삭제되었습니다.', 'info');
}

// 회사 전체를 메인 화면으로 불러오기
function loadCompanyToMain(companyId) {
    const savedCompanies = JSON.parse(localStorage.getItem('savedCompanyDrafts') || '[]');
    const company = savedCompanies.find(c => c.id === companyId);
    
    if (!company) return;
    
    const chatbot = window.emailChatbot;
    if (!chatbot) return;
    
    // 템플릿 섹션 표시
    document.getElementById('templatesSection').style.display = 'block';
    
    // 가상의 회사 데이터 생성
    const mockResult = {
        company: {
            '회사명': company.companyName
        },
        research: company.research,
        emails: {
            variations: {}
        }
    };
    
    // variations 객체 생성
    company.variations.forEach((variation, index) => {
        const key = `variation_${index}`;
        mockResult.emails.variations[key] = {
            ...variation
        };
    });
    
    // generatedResults에 추가
    if (!chatbot.generatedResults) {
        chatbot.generatedResults = [];
    }
    
    const loadedIndex = chatbot.generatedResults.length;
    chatbot.generatedResults.push(mockResult);
    
    // 메인 화면에 표시
    const container = document.getElementById('templatesContainer');
    const loadedDiv = document.createElement('div');
    loadedDiv.className = 'company-templates mb-4';
    loadedDiv.style.borderLeft = '4px solid #28a745';
    
    const timestamp = new Date().toLocaleTimeString('ko-KR');
    
    let variationsHtml = '';
    company.variations.forEach((variation, vIndex) => {
        variationsHtml += `
            <div class="col-md-6 mb-3">
                <div class="email-template" id="variation_${loadedIndex}_${vIndex}">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <h6 class="mb-0">
                            <i class="fas fa-bookmark text-success"></i> ${variation.type}
                        </h6>
                        <span class="personalization-score score-high">${variation.personalizationScore}/10</span>
                    </div>
                    <div class="mb-2">
                        <strong>제목:</strong>
                        <button class="btn btn-sm btn-outline-primary ms-2" onclick="copySubjectToClipboard('${variation.subject.replace(/'/g, "\\'")}')">
                            <i class="fas fa-copy"></i> 제목 복사
                        </button>
                        <br>
                        <em>${variation.subject}</em>
                    </div>
                    <div class="mb-3">
                        <strong>본문:</strong><br>
                        <div style="white-space: pre-line; word-break: keep-all; line-break: strict; font-size: 0.9em; max-height: 300px; overflow-y: auto; border: 1px solid #eee; padding: 10px; border-radius: 5px; line-height: 1.8;">
                            ${convertMarkdownToHtml(variation.body)}
                        </div>
                    </div>
                    <div class="d-flex gap-2 flex-wrap">
                        <button class="btn btn-sm btn-outline-primary" onclick="copyTextToClipboard('${variation.subject}', '${variation.body.replace(/'/g, "\\'").replace(/\n/g, "\\n")}')">
                            <i class="fas fa-copy"></i> 본문 복사
                        </button>
                        <button class="btn btn-sm btn-outline-secondary" onclick="refineEmailCopy(${loadedIndex}, ${vIndex})">
                            <i class="fas fa-edit"></i> 개선 요청
                        </button>
                    </div>
                    <textarea id="ai_template_${loadedIndex}_${vIndex}" style="position: absolute; left: -9999px;">
제목: ${variation.subject}

${variation.body}
                    </textarea>
                </div>
            </div>
        `;
    });
    
    loadedDiv.innerHTML = `
        <div class="company-info bg-light">
            <div class="d-flex justify-content-between align-items-center">
                <h5><i class="fas fa-building text-success"></i> 불러온 회사: ${company.companyName}</h5>
                <span class="badge bg-success">${company.variations.length}개 문안</span>
            </div>
            <small class="text-muted">불러온 시간: ${timestamp}</small>
            ${company.research.company_info ? `
                <div class="mt-2">
                    <small><strong>🔍 조사 결과:</strong></small>
                    <div class="small text-muted research-content" style="max-height: 200px; overflow-y: auto; white-space: pre-wrap; border: 1px solid #e9ecef; padding: 10px; border-radius: 5px; background-color: #f8f9fa;">
                        ${company.research.company_info}
                    </div>
                </div>
            ` : ''}
        </div>
        
        <div class="row">
            ${variationsHtml}
        </div>
    `;
    
    // 맨 위에 추가
    container.insertBefore(loadedDiv, container.firstChild);
    loadedDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
    
    // 사이드바 닫기
    toggleSidebar();
    
    chatbot.addBotMessage(`📂 "${company.companyName}"의 전체 문안 ${company.variations.length}개를 불러왔습니다!`);
    showToast('✅ 회사 데이터를 메인 화면으로 불러왔습니다!', 'success');
}

// 회사 상세보기 (모달에 표시)
function viewCompanyDetails(companyId) {
    const savedCompanies = JSON.parse(localStorage.getItem('savedCompanyDrafts') || '[]');
    const company = savedCompanies.find(c => c.id === companyId);
    
    if (!company) return;
    
    // 간단한 alert로 표시 (나중에 모달로 개선 가능)
    let details = `회사명: ${company.companyName}\n`;
    details += `저장일: ${new Date(company.savedAt).toLocaleString('ko-KR')}\n`;
    details += `문안 수: ${company.variations.length}개\n\n`;
    
    company.variations.forEach((v, i) => {
        details += `\n[${i+1}] ${v.type}\n`;
        details += `제목: ${v.subject}\n`;
        details += `점수: ${v.personalizationScore}/10\n`;
    });
    
    alert(details);
}

// 저장된 문안의 제목 복사
function copyDraftSubject(draftId) {
    const savedDrafts = JSON.parse(localStorage.getItem('savedEmailDrafts') || '[]');
    const draft = savedDrafts.find(d => d.id === draftId);
    
    if (draft) {
        copyToClipboard(draft.subject);
    }
}

// 저장된 문안의 본문 복사
function copyDraftBody(draftId) {
    const savedDrafts = JSON.parse(localStorage.getItem('savedEmailDrafts') || '[]');
    const draft = savedDrafts.find(d => d.id === draftId);
    
    if (draft) {
        const plainTextBody = htmlToPlainText(draft.body);
        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(plainTextBody).then(() => {
                showToast('본문이 클립보드에 복사되었습니다!', 'success');
            }).catch(err => {
                console.error('복사 실패:', err);
            });
        }
    }
}

// 저장된 문안 전체 복사
function copyFullDraft(draftId) {
    const savedDrafts = JSON.parse(localStorage.getItem('savedEmailDrafts') || '[]');
    const draft = savedDrafts.find(d => d.id === draftId);
    
    if (draft) {
        const plainTextBody = htmlToPlainText(draft.body);
        const fullText = `제목: ${draft.subject}\n\n${plainTextBody}`;
        
        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(fullText).then(() => {
                showToast('전체 문안이 클립보드에 복사되었습니다!', 'success');
            }).catch(err => {
                console.error('복사 실패:', err);
            });
        }
    }
}

// 문안 수정 모달 열기
let currentEditingDraftId = null;

function editDraft(draftId) {
    const savedDrafts = JSON.parse(localStorage.getItem('savedEmailDrafts') || '[]');
    const draft = savedDrafts.find(d => d.id === draftId);
    
    if (!draft) return;
    
    // 현재 수정 중인 ID 저장
    currentEditingDraftId = draftId;
    
    // 모달 필드에 데이터 채우기
    document.getElementById('editCompanyName').value = draft.companyName;
    document.getElementById('editVariationType').value = draft.variationType;
    document.getElementById('editSubject').value = draft.subject;
    document.getElementById('editBody').value = htmlToPlainText(draft.body);
    
    // 모달 열기
    document.getElementById('editModal').classList.add('active');
}

// 수정 모달 닫기
function closeEditModal() {
    document.getElementById('editModal').classList.remove('active');
    document.getElementById('aiRefinementRequest').value = ''; // 개선 요청 필드 초기화
    document.getElementById('aiRefineLoading').style.display = 'none'; // 로딩 숨김
    document.getElementById('restoreOriginalBtn').style.display = 'none'; // 되돌리기 버튼 숨김
    currentEditingDraftId = null;
    originalDraftBeforeRefinement = null; // 원본 데이터 초기화
}

// 모달 외부 클릭 시 닫기
function handleModalClick(event) {
    if (event.target.id === 'editModal') {
        closeEditModal();
    }
}

// 수정된 문안 저장
function saveEditedDraft() {
    if (!currentEditingDraftId) return;
    
    const savedDrafts = JSON.parse(localStorage.getItem('savedEmailDrafts') || '[]');
    const draftIndex = savedDrafts.findIndex(d => d.id === currentEditingDraftId);
    
    if (draftIndex === -1) return;
    
    // 수정된 내용 가져오기
    const editedSubject = document.getElementById('editSubject').value;
    const editedBody = document.getElementById('editBody').value;
    
    // 문안 업데이트 (HTML 태그는 그대로 유지하되 텍스트는 교체)
    savedDrafts[draftIndex].subject = editedSubject;
    savedDrafts[draftIndex].body = editedBody.replace(/\n/g, '<br>'); // 줄바꿈을 HTML로 변환
    
    // localStorage 업데이트
    localStorage.setItem('savedEmailDrafts', JSON.stringify(savedDrafts));
    
    // 사이드바 새로고침
    loadSavedDrafts();
    
    // 모달 닫기
    closeEditModal();
    
    // 성공 메시지
    showToast('✅ 문안이 수정되었습니다!', 'success');
}

// 개선 전 원본 저장용 변수
let originalDraftBeforeRefinement = null;

// AI로 저장된 문안 개선
async function aiRefineDraft() {
    if (!currentEditingDraftId) return;
    
    const currentBody = document.getElementById('editBody').value;
    const refinementRequest = document.getElementById('aiRefinementRequest').value.trim();
    
    if (!refinementRequest) {
        showToast('개선 요청사항을 입력해주세요.', 'error');
        return;
    }
    
    // 개선 전 원본 저장 (처음 개선 시에만)
    if (!originalDraftBeforeRefinement) {
        originalDraftBeforeRefinement = {
            subject: document.getElementById('editSubject').value,
            body: currentBody
        };
    }
    
    // 로딩 표시
    document.getElementById('aiRefineLoading').style.display = 'block';
    document.getElementById('aiRefineBtn').disabled = true;
    
    try {
        const response = await fetch('/api/refine-email', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                current_email: currentBody,
                refinement_request: refinementRequest
            })
        });
        
        if (!response.ok) {
            throw new Error(`API 오류: ${response.status}`);
        }
        
        const result = await response.json();
        
        if (result.success && result.refined_email) {
            // 개선된 내용을 본문 필드에 반영
            const plainText = htmlToPlainText(result.refined_email);
            document.getElementById('editBody').value = plainText;
            
            // 개선 요청 필드 초기화
            document.getElementById('aiRefinementRequest').value = '';
            
            // 되돌리기 버튼 표시
            document.getElementById('restoreOriginalBtn').style.display = 'inline-block';
            
            showToast('✅ AI가 문안을 개선했습니다!', 'success');
        } else {
            throw new Error(result.error || '개선 실패');
        }
    } catch (error) {
        console.error('AI 개선 오류:', error);
        showToast('❌ AI 개선 중 오류가 발생했습니다: ' + error.message, 'error');
    } finally {
        // 로딩 숨김
        document.getElementById('aiRefineLoading').style.display = 'none';
        document.getElementById('aiRefineBtn').disabled = false;
    }
}

// 개선 전 문안으로 되돌리기
function restoreOriginalDraft() {
    if (!originalDraftBeforeRefinement) {
        showToast('되돌릴 원본이 없습니다.', 'error');
        return;
    }
    
    // 원본으로 복원
    document.getElementById('editSubject').value = originalDraftBeforeRefinement.subject;
    document.getElementById('editBody').value = originalDraftBeforeRefinement.body;
    
    // 원본 데이터 초기화
    originalDraftBeforeRefinement = null;
    
    // 되돌리기 버튼 숨김
    document.getElementById('restoreOriginalBtn').style.display = 'none';
    
    showToast('✅ 개선 전 문안으로 되돌렸습니다!', 'success');
}

// ESC 키로 모달 닫기
document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
        closeEditModal();
    }
});

// 회사별 전체 저장 함수
function saveAllEmailsForCompany(companyIndex) {
    const chatbot = window.emailChatbot;
    if (!chatbot || !chatbot.generatedResults) return;
    
    const result = chatbot.generatedResults[companyIndex];
    if (!result) return;
    
    const companyName = result.company['회사명'];
    
    try {
        // localStorage에서 회사별 저장 데이터 가져오기
        let savedCompanies = JSON.parse(localStorage.getItem('savedCompanyDrafts') || '[]');
        
        // 4개 문안 모두 수집
        const allVariations = [];
        if (result.emails && result.emails.variations) {
            for (const [key, variation] of Object.entries(result.emails.variations)) {
                allVariations.push({
                    type: variation.type || key,
                    subject: variation.subject,
                    body: variation.body,
                    personalizationScore: variation.personalizationScore || 8.0
                });
            }
        }
        
        // 새 회사 데이터 생성
        const newCompanyData = {
            id: Date.now(),
            companyName: companyName,
            savedAt: new Date().toISOString(),
            research: {
                company_info: result.research?.company_info || '',
                pain_points: result.research?.pain_points || '',
                industry_trends: result.research?.industry_trends || '',
                timestamp: result.research?.timestamp || new Date().toISOString()
            },
            variations: allVariations
        };
        
        // 최신순으로 추가
        savedCompanies.unshift(newCompanyData);
        
        // 최대 50개 회사까지만 저장
        if (savedCompanies.length > 50) {
            savedCompanies = savedCompanies.slice(0, 50);
        }
        
        // localStorage에 저장
        localStorage.setItem('savedCompanyDrafts', JSON.stringify(savedCompanies));
        
        // 사이드바 업데이트
        loadSavedDrafts();
        
        // 성공 메시지
        showToast(`✅ ${companyName}의 전체 문안(${allVariations.length}개)이 저장되었습니다!`, 'success');
        
    } catch (error) {
        console.error('전체 저장 실패:', error);
        showToast('❌ 저장에 실패했습니다.', 'error');
    }
}

// 저장된 문안을 메인 화면으로 불러오기
function loadDraftToMain(draftId) {
    const savedDrafts = JSON.parse(localStorage.getItem('savedEmailDrafts') || '[]');
    const draft = savedDrafts.find(d => d.id === draftId);
    
    if (!draft) return;
    
    const chatbot = window.emailChatbot;
    if (!chatbot) return;
    
    // 템플릿 섹션 표시
    document.getElementById('templatesSection').style.display = 'block';
    
    // 가상의 회사 데이터와 이메일 결과 생성
    const mockResult = {
        company: {
            '회사명': draft.companyName
        },
        emails: {
            variations: {
                [draft.variationType]: {
                    type: draft.variationType,
                    subject: draft.subject,
                    body: draft.body,
                    personalizationScore: 9.0,
                    product: '저장된 문안'
                }
            }
        }
    };
    
    // generatedResults에 추가 (개선 요청 기능을 위해)
    if (!chatbot.generatedResults) {
        chatbot.generatedResults = [];
    }
    
    // 기존 결과를 대체하거나 새로 추가
    const loadedIndex = chatbot.generatedResults.length;
    chatbot.generatedResults.push(mockResult);
    
    // 메인 화면에 표시
    const container = document.getElementById('templatesContainer');
    
    const loadedDiv = document.createElement('div');
    loadedDiv.className = 'company-templates mb-4';
    loadedDiv.style.borderLeft = '4px solid #17a2b8';
    
    const timestamp = new Date().toLocaleTimeString('ko-KR');
    
    loadedDiv.innerHTML = `
        <div class="company-info bg-light">
            <div class="d-flex justify-content-between align-items-center">
                <h5><i class="fas fa-folder-open text-info"></i> 불러온 문안: ${draft.companyName}</h5>
                <span class="badge bg-info">${draft.variationType}</span>
            </div>
            <small class="text-muted">불러온 시간: ${timestamp}</small>
        </div>
        
        <div class="row">
            <div class="col-12 mb-3">
                <div class="email-template" id="variation_${loadedIndex}_0">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <h6 class="mb-0">
                            <i class="fas fa-bookmark text-info"></i> ${draft.variationType}
                            <br><small class="text-muted">저장된 문안</small>
                        </h6>
                        <span class="personalization-score score-high">9.0/10</span>
                    </div>
                    <div class="mb-2">
                        <strong>제목:</strong>
                        <button class="btn btn-sm btn-outline-primary ms-2" onclick="copySubjectToClipboard('${draft.subject.replace(/'/g, "\\'")}')">
                            <i class="fas fa-copy"></i> 제목 복사
                        </button>
                        <br>
                        <em>${draft.subject}</em>
                    </div>
                    <div class="mb-3">
                        <strong>본문:</strong><br>
                        <div style="white-space: pre-line; word-break: keep-all; line-break: strict; font-size: 0.9em; max-height: 300px; overflow-y: auto; border: 1px solid #eee; padding: 10px; border-radius: 5px; line-height: 1.8;">
                            ${convertMarkdownToHtml(draft.body)}
                        </div>
                    </div>
                    <div class="d-flex gap-2 flex-wrap">
                        <button class="btn btn-sm btn-outline-primary" onclick="copyTextToClipboard('${draft.subject}', '${draft.body.replace(/'/g, "\\'").replace(/\n/g, "\\n")}')">
                            <i class="fas fa-copy"></i> 본문 복사
                        </button>
                        <button class="btn btn-sm btn-outline-success" onclick="convertToHtmlTemplate('${draft.subject}', '${draft.body.replace(/'/g, "\\'").replace(/\n/g, "\\n")}', ${loadedIndex}, 0)">
                            <i class="fas fa-code"></i> HTML 템플릿
                        </button>
                        <button class="btn btn-sm btn-outline-secondary" onclick="refineEmailCopy(${loadedIndex}, 0)">
                            <i class="fas fa-edit"></i> 개선 요청
                        </button>
                        <button class="btn btn-sm btn-outline-warning" onclick="saveEmailDraft('${draft.companyName.replace(/'/g, "\\'")}', '${draft.variationType.replace(/'/g, "\\'")}', '${draft.subject.replace(/'/g, "\\'")}', '${draft.body.replace(/'/g, "\\'").replace(/\n/g, "\\n")}')">
                            <i class="fas fa-bookmark"></i> 다시 저장
                        </button>
                    </div>
                    <textarea id="ai_template_${loadedIndex}_0" style="position: absolute; left: -9999px;">
제목: ${draft.subject}

${draft.body}
                    </textarea>
                </div>
            </div>
        </div>
    `;
    
    // 맨 위에 추가
    container.insertBefore(loadedDiv, container.firstChild);
    
    // 스크롤하여 표시
    loadedDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
    
    // 사이드바 닫기
    toggleSidebar();
    
    // 챗봇 메시지 추가
    chatbot.addBotMessage(`📂 "${draft.companyName}"의 저장된 문안을 불러왔습니다. 이제 "개선 요청" 버튼으로 수정할 수 있습니다!`);
    
    showToast('✅ 문안을 메인 화면으로 불러왔습니다!', 'success');
}

// 챗봇 초기화
document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 Script.js 로드됨 - 현재 시간:', new Date().toLocaleTimeString());
    window.emailChatbot = new EmailCopywritingChatbot();
    
    // 저장된 문안 로드
    loadSavedDrafts();
    
    // 저장된 세션 목록 표시
    if (window.emailChatbot) {
        window.emailChatbot.updateSessionListUI();
    }
});

// ===== 안전한 버튼 함수들 (인덱스 기반) =====

// textarea에서 제목만 복사
function copySubjectFromTextarea(companyIndex, variationIndex) {
    const textarea = document.getElementById(`ai_template_${companyIndex}_${variationIndex}`);
    if (!textarea) {
        alert('문안을 찾을 수 없습니다.');
        return;
    }
    
    const content = textarea.value;
    const lines = content.split('\n');
    
    // 제목 추출
    let subject = '';
    if (lines[0] && lines[0].startsWith('제목:')) {
        subject = lines[0].replace('제목:', '').trim();
    } else {
        subject = '제목 없음';
    }
    
    copySubjectToClipboard(subject);
}

// textarea에서 내용을 가져와서 복사
function copyTemplateFromTextarea(companyIndex, variationIndex) {
    const textarea = document.getElementById(`ai_template_${companyIndex}_${variationIndex}`);
    if (!textarea) {
        alert('문안을 찾을 수 없습니다.');
        return;
    }
    
    const content = textarea.value;
    const lines = content.split('\n');
    
    // 제목과 본문 분리
    let subject = '';
    let body = '';
    
    if (lines[0] && lines[0].startsWith('제목:')) {
        subject = lines[0].replace('제목:', '').trim();
        body = lines.slice(2).join('\n').trim(); // 첫 줄(제목), 둘째 줄(빈 줄) 제외
    } else {
        subject = '제목 없음';
        body = content;
    }
    
    copyTextToClipboard(subject, body);
}

// textarea에서 내용을 가져와서 HTML 템플릿으로 변환
function convertToHtmlTemplateFromTextarea(companyIndex, variationIndex) {
    const textarea = document.getElementById(`ai_template_${companyIndex}_${variationIndex}`);
    if (!textarea) {
        alert('문안을 찾을 수 없습니다.');
        return;
    }
    
    const content = textarea.value;
    const lines = content.split('\n');
    
    // 제목과 본문 분리
    let subject = '';
    let body = '';
    
    if (lines[0] && lines[0].startsWith('제목:')) {
        subject = lines[0].replace('제목:', '').trim();
        body = lines.slice(2).join('\n').trim();
    } else {
        subject = '제목 없음';
        body = content;
    }
    
    convertToHtmlTemplate(subject, body, companyIndex, variationIndex);
}

// textarea에서 내용을 가져와서 저장
function saveEmailDraftFromTextarea(companyIndex, variationIndex) {
    const textarea = document.getElementById(`ai_template_${companyIndex}_${variationIndex}`);
    if (!textarea) {
        alert('문안을 찾을 수 없습니다.');
        return;
    }
    
    const content = textarea.value;
    const lines = content.split('\n');
    
    // 제목과 본문 분리
    let subject = '';
    let body = '';
    
    if (lines[0] && lines[0].startsWith('제목:')) {
        subject = lines[0].replace('제목:', '').trim();
        body = lines.slice(2).join('\n').trim();
    } else {
        subject = '제목 없음';
        body = content;
    }
    
    // 회사명과 문안 유형 추출
    const companyData = window.emailChatbot?.generatedResults?.[companyIndex];
    const companyName = companyData?.company?.['회사명'] || '알 수 없음';
    
    // variationType 추출
    let variationType = '알 수 없음';
    if (companyData?.emails?.variations) {
        const variationKeys = Object.keys(companyData.emails.variations);
        const variationKey = variationKeys[variationIndex];
        
        const typeNames = {
            'opi_professional': 'OPI - 전문적 톤',
            'opi_curiosity': 'OPI - 호기심 유발형',
            'finance_professional': '재무자동화 - 전문적 톤',
            'finance_curiosity': '재무자동화 - 호기심 유발형',
            'prism_professional': 'Prism - 전문적 톤',
            'prism_curiosity': 'Prism - 호기심 유발형',
            'game_d2c_professional': '게임 D2C - 전문적 톤',
            'game_d2c_curiosity': '게임 D2C - 호기심 유발형',
            'professional': '전문적 톤',
            'curiosity': '호기심 유발형',
            'value': '가치 제안형',
            'problem': '문제 해결형'
        };
        
        variationType = typeNames[variationKey] || variationKey;
    }
    
    saveEmailDraft(companyName, variationType, subject, body);
}

// ========================================
// 사용자 입력 모드 전환 및 히스토리 관리
// ========================================

// 모드 전환 함수
function switchUserInputMode(mode) {
    const chatbot = window.emailChatbot;
    if (!chatbot) return;
    
    chatbot.userInputMode = mode;
    
    const templateBtn = document.getElementById('templateModeBtn');
    const requestBtn = document.getElementById('requestModeBtn');
    const textarea = document.getElementById('userTemplate');
    const hint = document.getElementById('userInputHint');
    const historySection = document.getElementById('requestHistorySection');
    
    if (mode === 'template') {
        // 문안 모드
        templateBtn.classList.add('active');
        templateBtn.classList.remove('btn-outline-primary');
        templateBtn.classList.add('btn-primary');
        
        requestBtn.classList.remove('active');
        requestBtn.classList.remove('btn-success');
        requestBtn.classList.add('btn-outline-success');
        
        textarea.placeholder = '뉴스 후킹 서론과 함께 사용할 메일 본문 문안을 입력하세요. (입력한 문안의 90%가 그대로 사용됩니다)';
        hint.innerHTML = '💡 <strong>문안 모드:</strong> 뉴스 후킹 서론 + 입력한 본문(90% 유지) | <strong>비워두면:</strong> 뉴스 후킹 + 4개 생성 + SSR 추천';
        historySection.style.display = 'none';
    } else {
        // 요청사항 모드
        requestBtn.classList.add('active');
        requestBtn.classList.remove('btn-outline-success');
        requestBtn.classList.add('btn-success');
        
        templateBtn.classList.remove('active');
        templateBtn.classList.remove('btn-primary');
        templateBtn.classList.add('btn-outline-primary');
        
        textarea.placeholder = '예: 제목을 더 임팩트있게, 본문은 친근한 톤으로 작성하고, ROI 수치를 강조해주세요';
        hint.innerHTML = '💡 <strong>요청사항 모드:</strong> AI가 요청사항을 분석하여 맞춤 메일 생성 | <strong>비워두면:</strong> 뉴스 후킹 + 4개 생성 + SSR 추천';
        historySection.style.display = 'block';
    }
}

// 요청사항 히스토리 저장
function saveRequestToHistory(request) {
    if (!request || !request.trim()) return;
    
    let history = JSON.parse(localStorage.getItem('requestHistory') || '[]');
    
    // 중복 체크
    if (history.includes(request.trim())) {
        return;
    }
    
    // 최신 요청을 맨 앞에 추가
    history.unshift(request.trim());
    
    // 최대 20개까지만 저장
    if (history.length > 20) {
        history = history.slice(0, 20);
    }
    
    localStorage.setItem('requestHistory', JSON.stringify(history));
    loadRequestHistoryDropdown();
}

// 히스토리 드롭다운 로드
function loadRequestHistoryDropdown() {
    const select = document.getElementById('requestHistory');
    if (!select) return;
    
    const history = JSON.parse(localStorage.getItem('requestHistory') || '[]');
    
    // 기존 옵션 제거 (첫 번째 옵션 제외)
    while (select.options.length > 1) {
        select.remove(1);
    }
    
    // 히스토리 추가
    history.forEach((request, index) => {
        const option = document.createElement('option');
        option.value = index;
        // 긴 텍스트는 잘라서 표시
        const displayText = request.length > 50 ? request.substring(0, 50) + '...' : request;
        option.textContent = displayText;
        select.appendChild(option);
    });
}

// 히스토리에서 요청사항 불러오기
function loadRequestFromHistory(index) {
    if (index === '') return;
    
    const history = JSON.parse(localStorage.getItem('requestHistory') || '[]');
    const request = history[parseInt(index)];
    
    if (request) {
        document.getElementById('userTemplate').value = request;
        showToast('✅ 저장된 요청사항을 불러왔습니다!', 'success');
    }
}

// EmailCopywritingChatbot 클래스에 히스토리 로드 메서드 추가
EmailCopywritingChatbot.prototype.loadRequestHistory = function() {
    loadRequestHistoryDropdown();
};

// ========================================
// 챗봇 모드 - 재설득 메일 복사/저장
// ========================================

function copyChatEmail(companyName) {
    const subject = document.getElementById(`chat-subject-${companyName}`).innerText;
    const body = document.getElementById(`chat-body-${companyName}`).innerHTML;
    
    const emailText = `제목: ${subject}\n\n본문:\n${body.replace(/<br>/g, '\n').replace(/<[^>]*>/g, '')}`;
    
    navigator.clipboard.writeText(emailText).then(() => {
        showToast('📋 재설득 메일이 클립보드에 복사되었습니다!', 'success');
    }).catch(err => {
        console.error('복사 실패:', err);
        showToast('❌ 복사 중 오류가 발생했습니다.', 'danger');
    });
}

function saveChatEmail(companyName) {
    const subject = document.getElementById(`chat-subject-${companyName}`).innerText;
    const body = document.getElementById(`chat-body-${companyName}`).innerHTML;
    
    saveEmailDraft(companyName, '챗봇 재설득 메일', subject, body);
    showToast('💾 재설득 메일이 저장되었습니다!', 'success');
}

// 개선된 메일 복사
function copyRefinedEmail() {
    const subject = document.getElementById('refined-subject')?.innerText;
    const body = document.getElementById('refined-body')?.innerHTML;
    
    if (!subject || !body) {
        showToast('❌ 복사할 내용이 없습니다.', 'danger');
        return;
    }
    
    const emailText = `제목: ${subject}\n\n본문:\n${body.replace(/<br>/g, '\n').replace(/<strong>/g, '').replace(/<\/strong>/g, '').replace(/<[^>]*>/g, '')}`;
    
    navigator.clipboard.writeText(emailText).then(() => {
        showToast('📋 개선된 메일이 클립보드에 복사되었습니다!', 'success');
    }).catch(err => {
        console.error('복사 실패:', err);
        showToast('❌ 복사 중 오류가 발생했습니다.', 'danger');
    });
}

// ========================================
// 🆕 편집 모드 토글 및 일괄 발송 기능
// ========================================

/**
 * 편집 모드 토글
 */
function toggleEditMode(companyIndex, variationIndex) {
    const subjectDisplay = document.getElementById(`subject_display_${companyIndex}_${variationIndex}`);
    const subjectEdit = document.getElementById(`subject_edit_${companyIndex}_${variationIndex}`);
    const bodyDisplay = document.getElementById(`body_display_${companyIndex}_${variationIndex}`);
    const bodyEdit = document.getElementById(`body_edit_${companyIndex}_${variationIndex}`);
    const editButtons = document.getElementById(`edit_buttons_${companyIndex}_${variationIndex}`);
    
    if (!subjectDisplay || !subjectEdit || !bodyDisplay || !bodyEdit || !editButtons) {
        console.error('편집 모드 요소를 찾을 수 없습니다.');
        return;
    }
    
    // 처음 편집 모드 진입 시 HTML 백업 및 복사
    if (!bodyEdit.dataset.originalHtml) {
        // HTML 버전 백업
        bodyEdit.dataset.originalHtml = bodyDisplay.innerHTML;
        subjectEdit.dataset.originalText = subjectEdit.value;
        
        // contenteditable div에 HTML 그대로 복사 (특수문자 불필요!)
        bodyEdit.innerHTML = bodyDisplay.innerHTML;
    }
    
    // 편집 모드로 전환
    subjectDisplay.style.display = 'none';
    subjectEdit.style.display = 'block';
    bodyDisplay.style.display = 'none';
    bodyEdit.style.display = 'block';
    editButtons.style.display = 'block';
    
    // 사용 안내 표시
    const helpText = document.getElementById(`edit_help_${companyIndex}_${variationIndex}`);
    if (helpText) {
        helpText.style.display = 'block';
    }
    
    // 포커스 (contenteditable은 끝에 커서 위치)
    bodyEdit.focus();
    
    console.log(`편집 모드 활성화: Company ${companyIndex}, Variation ${variationIndex}`);
}

/**
 * 편집 모드 취소
 */
function cancelEditMode(companyIndex, variationIndex) {
    const subjectDisplay = document.getElementById(`subject_display_${companyIndex}_${variationIndex}`);
    const subjectEdit = document.getElementById(`subject_edit_${companyIndex}_${variationIndex}`);
    const bodyDisplay = document.getElementById(`body_display_${companyIndex}_${variationIndex}`);
    const bodyEdit = document.getElementById(`body_edit_${companyIndex}_${variationIndex}`);
    const editButtons = document.getElementById(`edit_buttons_${companyIndex}_${variationIndex}`);
    const helpText = document.getElementById(`edit_help_${companyIndex}_${variationIndex}`);
    
    // 원래 내용으로 복원 (contenteditable)
    if (bodyEdit.dataset.originalHtml) {
        bodyEdit.innerHTML = bodyEdit.dataset.originalHtml;
        subjectEdit.value = subjectEdit.dataset.originalText;
    }
    
    // 보기 모드로 전환
    subjectDisplay.style.display = 'block';
    subjectEdit.style.display = 'none';
    bodyDisplay.style.display = 'block';
    bodyEdit.style.display = 'none';
    editButtons.style.display = 'none';
    
    // 사용 안내 숨기기
    if (helpText) {
        helpText.style.display = 'none';
    }
    
    console.log(`편집 모드 취소: Company ${companyIndex}, Variation ${variationIndex}`);
}

/**
 * 편집된 이메일 저장
 */
function saveEditedEmail(companyIndex, variationIndex) {
    const subjectDisplay = document.getElementById(`subject_display_${companyIndex}_${variationIndex}`);
    const subjectEdit = document.getElementById(`subject_edit_${companyIndex}_${variationIndex}`);
    const bodyDisplay = document.getElementById(`body_display_${companyIndex}_${variationIndex}`);
    const bodyEdit = document.getElementById(`body_edit_${companyIndex}_${variationIndex}`);
    const editButtons = document.getElementById(`edit_buttons_${companyIndex}_${variationIndex}`);
    const helpText = document.getElementById(`edit_help_${companyIndex}_${variationIndex}`);
    
    // 수정된 내용 가져오기 (contenteditable에서 HTML 그대로)
    const newSubject = subjectEdit.value.trim();
    const newBodyHtml = bodyEdit.innerHTML.trim();
    
    if (!newSubject || !newBodyHtml) {
        showToast('❌ 제목과 본문을 모두 입력해주세요.', 'danger');
        return;
    }
    
    // HTML에서 텍스트 버전 추출 (저장용)
    const newBodyText = convertHtmlToFriendlyText(newBodyHtml);
    
    // 표시 영역 업데이트
    subjectDisplay.innerHTML = `<em>${newSubject}</em>`;
    bodyDisplay.innerHTML = newBodyHtml;
    
    // hidden textarea도 업데이트 (텍스트 버전 저장)
    const textarea = document.getElementById(`ai_template_${companyIndex}_${variationIndex}`);
    if (textarea) {
        textarea.value = `제목: ${newSubject}\n\n${newBodyText}`;
    }
    
    // 체크박스 데이터도 업데이트 (HTML 버전 저장)
    const checkbox = document.getElementById(`email_select_${companyIndex}_${variationIndex}`);
    if (checkbox) {
        checkbox.dataset.subject = newSubject;
        checkbox.dataset.body = newBodyHtml.replace(/\n/g, '\\n');
    }
    
    // 백업 업데이트 (HTML 버전)
    bodyEdit.dataset.originalHtml = newBodyHtml;
    subjectEdit.dataset.originalText = newSubject;
    
    // 보기 모드로 전환
    subjectDisplay.style.display = 'block';
    subjectEdit.style.display = 'none';
    bodyDisplay.style.display = 'block';
    bodyEdit.style.display = 'none';
    editButtons.style.display = 'none';
    
    // 사용 안내 숨기기
    if (helpText) {
        helpText.style.display = 'none';
    }
    
    showToast('✅ 이메일 문안이 저장되었습니다!', 'success');
    console.log(`이메일 저장 완료: Company ${companyIndex}, Variation ${variationIndex}`);
}

/**
 * AI 추천 문안 일괄 선택
 */
function selectAllRecommendedEmails() {
    // 모든 체크박스 찾기
    const allCheckboxes = document.querySelectorAll('input[id^="email_select_"]');
    
    // 먼저 모든 체크박스 해제
    allCheckboxes.forEach(checkbox => {
        checkbox.checked = false;
    });
    
    // AI 추천 문안만 선택 (isRecommended 뱃지가 있는 이메일 카드의 체크박스)
    let recommendedCount = 0;
    allCheckboxes.forEach(checkbox => {
        // 체크박스의 부모 요소에서 AI 추천 뱃지 찾기
        const emailCard = checkbox.closest('.email-template');
        if (emailCard) {
            const recommendedBadge = emailCard.querySelector('.badge.bg-success');
            // "AI 추천" 텍스트가 있는 뱃지인지 확인
            if (recommendedBadge && recommendedBadge.textContent.includes('AI 추천')) {
                checkbox.checked = true;
                recommendedCount++;
            }
        }
    });
    
    // 선택 개수 업데이트
    updateSelectedCount();
    
    // 사용자에게 피드백
    if (recommendedCount > 0) {
        const countBadge = document.getElementById('selectedEmailCount');
        if (countBadge) {
            countBadge.textContent = `${recommendedCount}개 AI 추천 문안 선택됨 ⭐`;
            countBadge.className = 'badge bg-warning';
            
            // 2초 후 원래 스타일로 돌아가기
            setTimeout(() => {
                countBadge.className = 'badge bg-success';
                countBadge.textContent = `${recommendedCount}개 선택됨`;
            }, 2000);
        }
    } else {
        alert('⚠️ AI 추천 문안이 없습니다.\n\nSSR(Semantic Similarity Rating) 기능이 활성화된 회사에서만 AI 추천 문안이 제공됩니다.');
    }
}

/**
 * 선택된 이메일 개수 표시
 */
function updateSelectedCount() {
    const checkboxes = document.querySelectorAll('input[id^="email_select_"]:checked');
    const button = document.getElementById('batchSendButton');
    const countBadge = document.getElementById('selectedEmailCount');
    
    const count = checkboxes.length;
    
    // 카운트 배지 업데이트
    if (countBadge) {
        if (count > 0) {
            countBadge.textContent = `${count}개 선택됨`;
            countBadge.className = 'badge bg-success';
        } else {
            countBadge.textContent = '0개 선택됨';
            countBadge.className = 'badge bg-secondary';
        }
    }
    
    // 버튼 상태 업데이트
    if (button) {
        if (count > 0) {
            button.innerHTML = `<i class="fas fa-paper-plane"></i> 선택한 ${count}개 문안 일괄 발송`;
            button.disabled = false;
            button.classList.remove('btn-secondary');
            button.classList.add('btn-primary');
        } else {
            button.innerHTML = '<i class="fas fa-paper-plane"></i> 일괄 발송 (문안을 선택해주세요)';
            button.disabled = true;
            button.classList.remove('btn-primary');
            button.classList.add('btn-secondary');
        }
    }
}

/**
 * 일괄 발송 전 Gmail 설정 확인
 */
async function checkGmailSettings() {
    try {
        const response = await fetch('/api/user/settings');
        const data = await response.json();
        return data.success && data.user.has_gmail_password;
    } catch (error) {
        console.error('설정 확인 오류:', error);
        return false;
    }
}

/**
 * 일괄 발송
 */
async function batchSendEmails() {
    const checkboxes = document.querySelectorAll('input[id^="email_select_"]:checked');
    
    if (checkboxes.length === 0) {
        showToast('❌ 발송할 이메일을 선택해주세요.', 'danger');
        return;
    }
    
    // Gmail 설정 확인
    const hasGmailPassword = await checkGmailSettings();
    if (!hasGmailPassword) {
        const userConfirm = confirm(
            '⚠️ Gmail 앱 비밀번호가 설정되지 않았습니다.\n\n' +
            '이메일을 발송하려면 Gmail 앱 비밀번호를 먼저 설정해야 합니다.\n\n' +
            '지금 설정 페이지로 이동하시겠습니까?'
        );
        
        if (userConfirm) {
            openSettingsModal();
        }
        return;
    }
    
    // 확인 대화상자
    const confirmMessage = `선택한 ${checkboxes.length}개의 이메일을 발송하시겠습니까?\n\n발송 대상:\n` + 
        Array.from(checkboxes).map((cb, idx) => 
            `${idx + 1}. ${cb.dataset.companyName} (${cb.dataset.email})`
        ).join('\n');
    
    if (!confirm(confirmMessage)) {
        return;
    }
    
    // 발송 준비
    const emailsToSend = [];
    
    checkboxes.forEach(checkbox => {
        const companyIndex = checkbox.dataset.companyIndex;
        const variationIndex = checkbox.dataset.variationIndex;
        const companyName = checkbox.dataset.companyName;
        const email = checkbox.dataset.email;
        
        // 현재 저장된 내용 가져오기 (saveEditedEmail에서 업데이트된 데이터)
        // checkbox.dataset에 저장된 최신 내용 사용
        let subject = checkbox.dataset.subject || '';
        let body = checkbox.dataset.body ? checkbox.dataset.body.replace(/\\n/g, '\n') : '';
        
        // dataset이 비어있으면 원본 데이터에서 가져오기
        if (!subject || !body) {
            if (window.emailChatbot && window.emailChatbot.generatedEmails) {
                const company = window.emailChatbot.generatedEmails[companyIndex];
                if (company && company.variations && company.variations[variationIndex]) {
                    const variation = company.variations[variationIndex];
                    subject = subject || variation.subject;
                    body = body || variation.body;
                }
            }
        }
        
        if (email && subject && body) {
            emailsToSend.push({
                companyName: companyName,
                email: email,
                subject: subject,
                body: body,
                companyIndex: companyIndex,
                variationIndex: variationIndex
            });
        }
    });
    
    if (emailsToSend.length === 0) {
        showToast('❌ 발송 가능한 이메일이 없습니다.', 'danger');
        return;
    }
    
    // 실제 발송 처리
    processBatchSend(emailsToSend);
}

/**
 * 일괄 발송 처리 (로그인된 사용자가 발신자)
 */
async function processBatchSend(emails) {
    const progressModal = showProgressModal(emails.length);
    let successCount = 0;
    let failCount = 0;
    
    for (let i = 0; i < emails.length; i++) {
        const emailData = emails[i];
        
        try {
            updateProgress(i + 1, emails.length, emailData.companyName);
            
            // 실제 이메일 발송 API 호출
            await sendEmailAPI(emailData);
            
            successCount++;
            
            // 체크박스 해제
            const checkbox = document.getElementById(`email_select_${emailData.companyIndex}_${emailData.variationIndex}`);
            if (checkbox) checkbox.checked = false;
            
        } catch (error) {
            console.error(`발송 실패: ${emailData.companyName}`, error);
            failCount++;
        }
    }
    
    // 진행상황 모달 닫기
    closeProgressModal();
    
    // 결과 표시
    const resultMessage = `발송 완료!\n\n성공: ${successCount}건\n실패: ${failCount}건`;
    alert(resultMessage);
    
    // 선택 개수 업데이트
    updateSelectedCount();
    
    showToast(`✅ ${successCount}개 이메일 발송 완료!`, 'success');
}

/**
 * 이메일 발송 API 호출
 * 로그인된 사용자의 이메일을 발신자로 사용
 */
async function sendEmailAPI(emailData) {
    try {
        const response = await fetch('/api/send-email', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                to_email: emailData.email,
                to_name: emailData.companyName,
                subject: emailData.subject,
                body: emailData.body
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || '발송 실패');
        }
        
        const result = await response.json();
        console.log(`✅ 발송 성공: ${emailData.companyName} (${emailData.email})`);
        return result;
        
    } catch (error) {
        console.error(`❌ 발송 실패: ${emailData.companyName}`, error);
        throw error;
    }
}

/**
 * 진행상황 모달 표시
 */
function showProgressModal(total) {
    const modal = document.createElement('div');
    modal.id = 'progressModal';
    modal.className = 'modal fade show';
    modal.style.display = 'block';
    modal.innerHTML = `
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title"><i class="fas fa-paper-plane"></i> 이메일 발송 중...</h5>
                </div>
                <div class="modal-body text-center">
                    <div class="progress mb-3" style="height: 30px;">
                        <div id="sendProgress" class="progress-bar progress-bar-striped progress-bar-animated" 
                             role="progressbar" style="width: 0%">0%</div>
                    </div>
                    <p id="progressText">준비 중...</p>
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                </div>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
    
    const backdrop = document.createElement('div');
    backdrop.id = 'progressBackdrop';
    backdrop.className = 'modal-backdrop fade show';
    document.body.appendChild(backdrop);
    
    return modal;
}

/**
 * 진행상황 업데이트
 */
function updateProgress(current, total, companyName) {
    const percent = Math.round((current / total) * 100);
    const progressBar = document.getElementById('sendProgress');
    const progressText = document.getElementById('progressText');
    
    if (progressBar) {
        progressBar.style.width = percent + '%';
        progressBar.textContent = percent + '%';
    }
    
    if (progressText) {
        progressText.textContent = `${current}/${total} - ${companyName}에게 발송 중...`;
    }
}

/**
 * 진행상황 모달 닫기
 */
function closeProgressModal() {
    const modal = document.getElementById('progressModal');
    const backdrop = document.getElementById('progressBackdrop');
    
    if (modal) modal.remove();
    if (backdrop) backdrop.remove();
}

// ========================================
// 🆕 사용자 설정 기능
// ========================================

/**
 * 설정 모달 열기
 */
async function openSettingsModal() {
    try {
        // 현재 설정 조회
        const response = await fetch('/api/user/settings');
        const data = await response.json();
        
        if (data.success) {
            // Gmail 비밀번호 상태 표시
            const gmailStatusBadge = document.getElementById('gmailStatus');
            if (data.user.has_gmail_password) {
                gmailStatusBadge.textContent = '설정됨 ✓';
                gmailStatusBadge.className = 'badge bg-success ms-2';
            } else {
                gmailStatusBadge.textContent = '미설정';
                gmailStatusBadge.className = 'badge bg-secondary ms-2';
            }
            
            // SendGrid API 키 상태 표시
            const sendgridStatusBadge = document.getElementById('sendgridStatus');
            if (data.user.has_sendgrid_api_key) {
                sendgridStatusBadge.textContent = '설정됨 ✓';
                sendgridStatusBadge.className = 'badge bg-success ms-2';
            } else {
                sendgridStatusBadge.textContent = '미설정';
                sendgridStatusBadge.className = 'badge bg-secondary ms-2';
            }
        }
        
        // 모달 열기
        const modal = new bootstrap.Modal(document.getElementById('settingsModal'));
        modal.show();
        
    } catch (error) {
        console.error('설정 조회 오류:', error);
        showToast('❌ 설정을 불러올 수 없습니다.', 'danger');
    }
}

/**
 * 설정 새로고침 (저장 후 호출)
 */
async function loadUserSettings() {
    // openSettingsModal과 동일한 로직이지만 모달은 열지 않음
    try {
        const response = await fetch('/api/user/settings');
        const data = await response.json();
        
        if (data.success) {
            // Gmail 비밀번호 상태 표시
            const gmailStatusBadge = document.getElementById('gmailStatus');
            if (gmailStatusBadge) {
                if (data.user.has_gmail_password) {
                    gmailStatusBadge.textContent = '설정됨 ✓';
                    gmailStatusBadge.className = 'badge bg-success ms-2';
                } else {
                    gmailStatusBadge.textContent = '미설정';
                    gmailStatusBadge.className = 'badge bg-secondary ms-2';
                }
            }
            
            // SendGrid API 키 상태 표시
            const sendgridStatusBadge = document.getElementById('sendgridStatus');
            if (sendgridStatusBadge) {
                if (data.user.has_sendgrid_api_key) {
                    sendgridStatusBadge.textContent = '설정됨 ✓';
                    sendgridStatusBadge.className = 'badge bg-success ms-2';
                } else {
                    sendgridStatusBadge.textContent = '미설정';
                    sendgridStatusBadge.className = 'badge bg-secondary ms-2';
                }
            }
        }
    } catch (error) {
        console.error('설정 새로고침 오류:', error);
    }
}

/**
 * 설정 저장
 */
async function saveSettings() {
    const gmailPassword = document.getElementById('gmailPassword').value.trim();
    const sendgridApiKey = document.getElementById('sendgridApiKey').value.trim();
    
    // 둘 중 하나는 입력되어야 함
    if (!gmailPassword && !sendgridApiKey) {
        showToast('❌ Gmail 앱 비밀번호 또는 SendGrid API 키를 입력해주세요.', 'danger');
        return;
    }
    
    // SendGrid API 키 형식 검증
    if (sendgridApiKey) {
        if (sendgridApiKey.startsWith('SK.')) {
            showToast('❌ Twilio API 키(SK.로 시작)는 사용할 수 없습니다. SendGrid API 키(SG.로 시작)를 입력해주세요.', 'danger');
            return;
        }
        
        if (!sendgridApiKey.startsWith('SG.')) {
            showToast('⚠️ SendGrid API 키는 반드시 "SG."로 시작해야 합니다. API 키를 다시 확인해주세요.', 'warning');
            return;
        }
        
        if (sendgridApiKey.length < 20) {
            showToast('⚠️ SendGrid API 키가 너무 짧습니다. 올바른 형식인지 확인해주세요.', 'warning');
            return;
        }
    }
    
    try {
        const payload = {};
        if (gmailPassword) {
            payload.gmail_app_password = gmailPassword;
        }
        if (sendgridApiKey) {
            payload.sendgrid_api_key = sendgridApiKey;
        }
        
        const response = await fetch('/api/user/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });
        
        const data = await response.json();
        
        if (data.success) {
            // 모달 닫기 (토스트보다 먼저)
            const modal = bootstrap.Modal.getInstance(document.getElementById('settingsModal'));
            modal.hide();
            
            // 입력창 초기화
            document.getElementById('gmailPassword').value = '';
            document.getElementById('sendgridApiKey').value = '';
            
            // 설정 상태 새로고침
            loadUserSettings();
            
            // 모달이 완전히 닫힌 후 토스트 표시 (300ms 지연)
            setTimeout(() => {
                showToast('✅ ' + data.message, 'success');
            }, 300);
            
        } else {
            showToast('❌ ' + data.error, 'danger');
        }
        
    } catch (error) {
        console.error('설정 저장 오류:', error);
        showToast('❌ 설정 저장 중 오류가 발생했습니다.', 'danger');
    }
}

// ========================================
// 전역 함수 노출 (HTML onclick에서 호출 가능하도록)
// ========================================
window.openSettingsModal = openSettingsModal;
window.saveSettings = saveSettings;
