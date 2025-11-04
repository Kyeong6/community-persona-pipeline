# GitHub Actions 크롤링 자동화

## 개요
- **실행 주기**: 매주 월요일 오전 2시 (UTC) = 한국시간 오전 11시
- **예상 실행 시간**: 약 2시간
- **제한**: GitHub Actions 최대 실행 시간 6시간 내에서 충분히 가능

## 설정 방법

### 1. GitHub Secrets 설정
Repository Settings → Secrets and variables → Actions에서 다음 secrets 추가:

#### 크롤링 관련
- `NAVER_COOKIE`: 네이버 로그인 쿠키 (선택사항, 있으면 자동 로그인 우회)
- `NAVER_ID`: 네이버 아이디 (NAVER_COOKIE가 없을 때만 필요)
- `NAVER_PASSWORD`: 네이버 비밀번호 (NAVER_COOKIE가 없을 때만 필요)

#### 서버 배포 관련
- `SERVER_HOST`: 운영 서버 호스트 (예: `192.168.1.100` 또는 `server.example.com`)
- `SERVER_USER`: 서버 접속 사용자명 (예: `ubuntu`, `deploy`)
- `SERVER_SSH_KEY`: SSH 개인키 (전체 내용, `-----BEGIN RSA PRIVATE KEY-----` 포함)
- `SERVER_PORT`: SSH 포트 (기본값: 22, 선택사항)
- `SERVER_TARGET_PATH`: 서버에 파일을 저장할 경로 (예: `/home/deploy/crawling-results`, 기본값: `/tmp/crawling-results`)
- `SERVER_UPDATE_SCRIPT`: 파일 전송 후 실행할 스크립트 (선택사항, 예: `cd /app && python update_data.py`)

### 2. SSH 키 생성 및 설정

#### SSH 키 생성 (로컬에서)
```bash
ssh-keygen -t rsa -b 4096 -C "github-actions" -f ~/.ssh/github_actions_key
```

#### 공개키를 서버에 등록
```bash
# 서버에 접속하여
cat ~/.ssh/github_actions_key.pub >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

#### GitHub Secrets에 개인키 등록
1. GitHub Repository → Settings → Secrets and variables → Actions
2. New repository secret 클릭
3. Name: `SERVER_SSH_KEY`
4. Value: `~/.ssh/github_actions_key` 파일의 전체 내용 복사 (BEGIN/END 포함)

### 3. 서버 업데이트 스크립트 예시

서버에서 데이터를 업데이트하는 스크립트 예시:

```bash
#!/bin/bash
# /home/deploy/update_crawling_data.sh

# 크롤링 결과 파일을 애플리케이션으로 복사
cp /tmp/crawling-results/*.json /app/data/crawling/

# 데이터베이스 업데이트 (예시)
cd /app
python manage.py update_crawling_data /app/data/crawling/

# 또는 API 호출로 업데이트
# curl -X POST https://api.example.com/update-crawling-data \
#   -H "Authorization: Bearer $API_TOKEN" \
#   -F "file=@/tmp/crawling-results/latest.json"
```

그리고 GitHub Secrets의 `SERVER_UPDATE_SCRIPT`에:
```
cd /home/deploy && bash update_crawling_data.sh
```

### 4. 수동 실행
Actions 탭에서 "Weekly Crawling" 워크플로우 선택 → "Run workflow" 클릭

### 5. 결과 확인
- Actions 탭에서 실행 결과 확인
- Artifacts에서 결과 파일 다운로드 가능
- 서버의 `SERVER_TARGET_PATH`에서 결과 파일 확인

## 서버 배포 설정

### SSH 키 생성 및 설정

#### SSH 키 생성 (로컬에서)
```bash
ssh-keygen -t rsa -b 4096 -C "github-actions" -f ~/.ssh/github_actions_key
```

#### 공개키를 서버에 등록
```bash
# 서버에 접속하여
cat ~/.ssh/github_actions_key.pub >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

#### GitHub Secrets에 개인키 등록
1. GitHub Repository → Settings → Secrets and variables → Actions
2. New repository secret 클릭
3. Name: `SERVER_SSH_KEY`
4. Value: `~/.ssh/github_actions_key` 파일의 전체 내용 복사 (BEGIN/END 포함)

### 서버 업데이트 스크립트 예시

서버에서 데이터를 업데이트하는 스크립트 예시:

```bash
#!/bin/bash
# /home/deploy/update_crawling_data.sh

# 크롤링 결과 파일을 애플리케이션으로 복사
cp /tmp/crawling-results/*.json /app/data/crawling/

# 데이터베이스 업데이트 (예시)
cd /app
python manage.py update_crawling_data /app/data/crawling/

# 또는 API 호출로 업데이트
# curl -X POST https://api.example.com/update-crawling-data \
#   -H "Authorization: Bearer $API_TOKEN" \
#   -F "file=@/tmp/crawling-results/latest.json"
```

그리고 GitHub Secrets의 `SERVER_UPDATE_SCRIPT`에:
```
cd /home/deploy && bash update_crawling_data.sh
```

## 주의사항
- GitHub Actions는 headless 모드로 실행됩니다
- 네이버 로그인은 NAVER_COOKIE 사용을 권장합니다 (더 안정적)
- 실행 시간이 2시간 이상 걸릴 수 있으므로 timeout-minutes는 240으로 설정했습니다
- SSH 키는 반드시 Secrets에 저장하고 Git에 커밋하지 마세요
- 서버 스크립트는 실행 권한이 있어야 합니다 (`chmod +x`)

## 보안 권장사항
1. SSH 키는 읽기 전용 권한으로 생성
2. 서버에서 GitHub Actions 전용 사용자 계정 생성 권장
3. 방화벽에서 특정 IP만 허용 (GitHub Actions IP 범위 확인 필요)

