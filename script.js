// 메일 문안 생성 챗봇 JavaScript

class EmailCopywritingChatbot {
    constructor() {
        this.uploadedData = [];
        this.currentCompanyIndex = 0;
        this.isRefinementMode = false;
        this.currentRefinementTarget = null;
        this.initializeEventListeners();
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
                '글로벌 결제 지원',
                '구독 모델 최적화',
                '결제 전환율 개선'
            ],
            startup: [
                '제한된 개발 리소스',
                '빠른 MVP 출시 필요',
                '비용 효율성',
                '확장성 확보'
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
        
        // Enter 키 이벤트
        userInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
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
        if (!file.name.toLowerCase().endsWith('.csv')) {
            this.addBotMessage('❌ CSV 파일만 업로드 가능합니다.');
            return;
        }

        const reader = new FileReader();
        reader.onload = (e) => {
            try {
                const csv = e.target.result;
                this.uploadedData = this.parseCSV(csv);
                this.displayFileInfo(file.name, this.uploadedData.length);
                this.addBotMessage(`✅ ${file.name} 파일이 성공적으로 업로드되었습니다. 총 ${this.uploadedData.length}개 회사 데이터를 확인했습니다.`);
                document.getElementById('generateBtn').disabled = false;
            } catch (error) {
                this.addBotMessage('❌ 파일 처리 중 오류가 발생했습니다: ' + error.message);
            }
        };
        reader.readAsText(file, 'utf-8');
    }

    parseCSV(csv) {
        const lines = csv.split('\n').filter(line => line.trim());
        const headers = lines[0].split(',').map(h => h.trim());
        const data = [];

        for (let i = 1; i < lines.length; i++) {
            const values = lines[i].split(',').map(v => v.trim());
            const row = {};
            headers.forEach((header, index) => {
                row[header] = values[index] || '';
            });
            
            // 필수 필드가 있는 행만 포함
            if (row['회사명'] && row['회사명'].trim() !== '') {
                data.push(row);
            }
        }

        return data;
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
            
            // 백엔드 API로 병렬 처리 요청
            const response = await fetch('http://localhost:5001/api/batch-process', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    companies: companiesToProcess,
                    max_workers: maxWorkers
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
        
        let progress = 0;
        const increment = 100 / (total * 2); // 천천히 증가
        
        const interval = setInterval(() => {
            progress += increment;
            if (progress > 95) progress = 95; // 95%에서 멈춤
            
            progressBar.style.width = `${progress}%`;
            progressText.textContent = `${Math.round(progress)}% 완료 중...`;
            
            if (progress >= 95) {
                clearInterval(interval);
                progressText.textContent = '거의 완료...';
            }
        }, 500);
        
        // 인스턴스에 저장하여 나중에 정리할 수 있도록
        this.progressInterval = interval;
    }

    removeProgressIndicator() {
        const progressElement = document.getElementById('progressIndicator');
        if (progressElement) {
            progressElement.remove();
        }
        
        if (this.progressInterval) {
            clearInterval(this.progressInterval);
            this.progressInterval = null;
        }
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
        const contactName = company['대표자명'] || company['담당자명'] || '담당자';
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
        const container = document.getElementById('templatesContainer');
        container.innerHTML = '';
        
        // 결과를 인스턴스 변수에 저장하여 CSV 다운로드에서 사용
        this.generatedResults = results;
        
        results.forEach((result, index) => {
            if (result.error) {
                // 오류가 있는 경우
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
                                product: value.product || 'PortOne 솔루션',
                                subject: value.subject || '제목 없음',
                                body: value.body || '본문 없음',
                                cta: value.cta || '',
                                tone: value.tone || '',
                                personalizationScore: value.personalization_score || this.calculateAIScore(result.research, value)
                            };
                        });
                    } else {
                        // JSON 파싱 실패 시 텍스트를 3개 스타일로 분할 시도
                        const textContent = variations.raw_content || variations || '';
                        emailVariations = this.parseTextToVariations(textContent, result.company['회사명']);
                    }
                } catch (e) {
                    console.error('이메일 파싱 오류:', e);
                    // 완전 실패 시 기본 템플릿 제공
                    const contactName = result.company['대표자명'] || result.company['담당자명'] || '담당자';
                    const contactPosition = result.company['직책'] || result.company['직급'] || '';
                    const personalizedGreeting = this.generatePersonalizedGreeting(contactName, contactPosition, result.company['회사명']);
                    emailVariations = this.createFallbackVariations(result.company['회사명'], personalizedGreeting);
                }
            }
            
            companyDiv.innerHTML = `
                <div class="company-info">
                    <h5><i class="fas fa-building"></i> ${result.company['회사명']}</h5>
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
                            <button class="btn btn-sm btn-outline-primary mt-2" onclick="toggleResearchContent(this)">
                                <i class="fas fa-expand-alt"></i> 전체 내용 보기
                            </button>
                        </div>
                    ` : ''}
                </div>
                
                <div class="row">
                    ${emailVariations.map((variation, vIndex) => `
                        <div class="col-md-${emailVariations.length === 1 ? '12' : '6'} mb-3">
                            <div class="email-template">
                                <div class="d-flex justify-content-between align-items-center mb-2">
                                    <h6 class="mb-0">
                                        <i class="fas fa-robot text-primary"></i> ${variation.type}
                                        ${variation.product ? `<br><small class="text-muted">${variation.product}</small>` : ''}
                                    </h6>
                                    <span class="personalization-score ${this.getScoreClass(variation.personalizationScore)}">
                                        ${variation.personalizationScore}/10
                                    </span>
                                </div>
                                <div class="mb-2">
                                    <strong>제목:</strong><br>
                                    <em>${variation.subject}</em>
                                </div>
                                <div class="mb-3">
                                    <strong>본문:</strong><br>
                                    <div style="white-space: pre-line; font-size: 0.9em; max-height: 300px; overflow-y: auto; border: 1px solid #eee; padding: 10px; border-radius: 5px;">
                                        ${variation.body}
                                    </div>
                                </div>
                                <div class="d-flex gap-2 flex-wrap">
                                    <button class="btn btn-sm btn-outline-primary" onclick="copyTextToClipboard('${variation.subject}', '${variation.body.replace(/'/g, "\\'").replace(/\n/g, "\\n")}')">
                                        <i class="fas fa-copy"></i> 텍스트 복사
                                    </button>
                                    <button class="btn btn-sm btn-outline-success" onclick="convertToHtmlTemplate('${variation.subject}', '${variation.body.replace(/'/g, "\\'").replace(/\n/g, "\\n")}', ${index}, ${vIndex})">
                                        <i class="fas fa-code"></i> HTML 템플릿
                                    </button>
                                    <button class="btn btn-sm btn-outline-secondary" onclick="refineEmailCopy(${index}, ${vIndex})">
                                        <i class="fas fa-edit"></i> 개선 요청
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
        
        // 컨테이너 맨 위에 추가
        container.insertBefore(downloadSection, container.firstChild);
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
                                row.push(`"${String(variations[i].body).replace(/"/g, '""')}"`);
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

    // 개선된 이메일 표시
    displayRefinedEmail(refinedEmail, request) {
        const container = document.getElementById('templatesContainer');
        
        const refinedDiv = document.createElement('div');
        refinedDiv.className = 'company-templates mb-4 border-success';
        refinedDiv.style.borderLeft = '4px solid #28a745';
        
        const timestamp = new Date().toLocaleTimeString('ko-KR');
        const refinedId = `refined_${Date.now()}`;
        
        refinedDiv.innerHTML = `
            <div class="company-info bg-light">
                <h5><i class="fas fa-magic text-success"></i> 개선된 이메일 문안</h5>
                <div class="row">
                    <div class="col-md-6">
                        <small><strong>개선 요청:</strong> ${request}</small>
                    </div>
                    <div class="col-md-6">
                        <small><strong>생성 시간:</strong> ${timestamp}</small>
                    </div>
                </div>
            </div>
            
            <div class="row">
                <div class="col-12">
                    <div class="email-template border-success">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <h6 class="mb-0">
                                <i class="fas fa-sparkles text-success"></i> AI 개선 문안
                            </h6>
                            <span class="badge bg-success">개선됨</span>
                        </div>
                        <div class="mb-3">
                            <div style="white-space: pre-line; font-size: 0.9em; max-height: 400px; overflow-y: auto; border: 1px solid #28a745; padding: 15px; border-radius: 5px; background-color: #f8fff9;">
                                ${refinedEmail}
                            </div>
                        </div>
                        <div class="d-flex gap-2">
                            <button class="btn btn-sm btn-success" onclick="copyToClipboard('${refinedId}')">
                                <i class="fas fa-copy"></i> 개선된 문안 복사
                            </button>
                        </div>
                        <textarea id="${refinedId}" style="position: absolute; left: -9999px;">${refinedEmail}</textarea>
                    </div>
                </div>
            </div>
        `;
        
        // 맨 위에 추가
        container.insertBefore(refinedDiv, container.firstChild);
        
        // 스크롤을 맨 위로 이동
        refinedDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
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
        messageDiv.textContent = message;
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

    handleUserMessage(message) {
        // 개선 모드인지 확인
        if (this.isRefinementMode && this.currentRefinementTarget) {
            this.processRefinementRequest(message);
            return;
        }

        const lowerMessage = message.toLowerCase();
        
        if (lowerMessage.includes('다시') || lowerMessage.includes('재생성')) {
            this.addBotMessage('새로운 메일 문안을 생성하려면 "메일 문안 생성하기" 버튼을 다시 클릭해주세요.');
        } else if (lowerMessage.includes('도움') || lowerMessage.includes('사용법')) {
            this.addBotMessage(`
사용 방법 안내:
1. CSV 파일 업로드 (회사명, 이메일 등 포함)
2. "메일 문안 생성하기" 버튼 클릭
3. 생성된 문안 중 마음에 드는 것 선택
4. "개선 요청" 버튼 클릭 후 위 텍스트박스에 요청사항 입력
5. "복사" 버튼으로 클립보드에 복사

추가 질문이 있으시면 언제든 말씀해주세요!
            `);
        } else {
            this.addBotMessage('죄송합니다. 아직 해당 요청을 처리할 수 없습니다. "도움말"을 입력하시면 사용 방법을 안내해드립니다.');
        }
    }

    async processRefinementRequest(refinementRequest) {
        if (!refinementRequest.trim()) {
            this.addBotMessage('개선 요청사항을 입력해주세요.');
            return;
        }

        this.addBotMessage(`🔄 "${refinementRequest}" 요청에 따라 이메일 문안을 개선하고 있습니다...`);
        this.showLoading(true);
        
        try {
            // 현재 이메일 내용 가져오기
            const { companyIndex, variationIndex } = this.currentRefinementTarget;
            const templateElement = document.getElementById(`ai_template_${companyIndex}_${variationIndex}`);
            const currentContent = templateElement ? templateElement.value : '';
            
            // 백엔드 API로 개선 요청
            const response = await fetch('http://localhost:5001/api/refine-email', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    current_email: currentContent,
                    refinement_request: refinementRequest
                })
            });
            
            if (!response.ok) {
                throw new Error(`API 오류: ${response.status}`);
            }
            
            const result = await response.json();
            
            if (result.success) {
                // 개선된 내용을 새로운 템플릿으로 표시
                this.displayRefinedEmail(result.refined_email, refinementRequest);
                this.addBotMessage('✅ 이메일 문안 개선이 완료되었습니다!');
            } else {
                throw new Error(result.error || '개선 요청 처리 실패');
            }
            
        } catch (error) {
            this.addBotMessage('❌ 이메일 개선 중 오류가 발생했습니다: ' + error.message);
        } finally {
            this.showLoading(false);
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
        userInput.placeholder = '개선 요청사항을 입력하세요 (예: "더 친근하게", "기술적 내용 추가", "짧게 요약")';
        userInput.focus();
        sendBtn.disabled = false;
        
        this.addBotMessage('💡 위 텍스트박스에 개선 요청사항을 입력하고 전송 버튼을 눌러주세요!');
    }

    exitRefinementMode() {
        this.isRefinementMode = false;
        this.currentRefinementTarget = null;
        
        const userInput = document.getElementById('userInput');
        const sendBtn = document.getElementById('sendBtn');
        
        userInput.value = '';
        userInput.placeholder = '추가 요청사항이나 질문을 입력하세요...';
        
        // 이메일 생성이 완료되었으면 계속 활성화 유지
        if (this.uploadedData.length > 0) {
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

    clearChat() {
        const chatContainer = document.getElementById('chatContainer');
        chatContainer.innerHTML = `
            <div class="message bot-message">
                <strong>PortOne 메일 봇</strong><br>
                대화가 초기화되었습니다. 새로운 메일 문안 생성을 시작해보세요! 👋
            </div>
        `;
    }

    showLoading(show) {
        document.getElementById('loadingIndicator').style.display = show ? 'block' : 'none';
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

// 텍스트 복사 함수 (개선된 버전)
function copyTextToClipboard(subject, body) {
    // 1. <br> 태그를 줄바꿈 문자(\n)로 변환합니다.
    const bodyWithNewlines = body.replace(/<br\s*\/?>/gi, '\n');

    // 2. 임시 DOM 요소를 사용해 나머지 HTML 태그를 제거합니다.
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = bodyWithNewlines;
    const plainBody = tempDiv.textContent || tempDiv.innerText || "";

    // 3. 순수 텍스트로 제목과 본문을 조합합니다.
    const fullText = `제목: ${subject}\n\n${plainBody}`;
    
    // 최신 브라우저의 Clipboard API 사용
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(fullText).then(() => {
            showCopySuccess('텍스트가 클립보드에 복사되었습니다!');
        }).catch(err => {
            console.error('복사 실패:', err);
            fallbackCopyTextToClipboard(fullText);
        });
    } else {
        // 폴백 방법
        fallbackCopyTextToClipboard(fullText);
    }
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
        showCopySuccess('텍스트가 클립보드에 복사되었습니다!');
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

// 챗봇 초기화
document.addEventListener('DOMContentLoaded', () => {
    window.emailChatbot = new EmailCopywritingChatbot();
});
