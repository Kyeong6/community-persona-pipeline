# 커뮤니티 크롤링 MCP 서버

이 프로젝트는 Playwright와 MCP(Model Context Protocol)를 사용하여 한국의 주요 커뮤니티 사이트에서 인기글을 크롤링하는 서버입니다.

## 지원 커뮤니티

- **맘이베베**: 네이버 카페 기반 커뮤니티
- **뽐뿌**: 쇼핑 정보 커뮤니티  
- **에펨코리아**: 종합 커뮤니티

## 설치 및 실행

### 1. 의존성 설치
```bash
poetry install
poetry run playwright install
```

### 2. 환경변수 설정
```bash
cp env.example .env
# .env 파일을 편집하여 설정값 조정
```

### 3. MCP 서버 실행
```bash
poetry run crawl
```

## 사용 가능한 도구

- `crawl_mamibebe`: 맘이베베 인기글 크롤링
- `crawl_ppomppu`: 뽐뿌 인기글 크롤링  
- `crawl_fmkorea`: 에펨코리아 인기글 크롤링
- `crawl_all`: 모든 커뮤니티 동시 크롤링

## 데이터 구조

각 게시글은 다음 정보를 포함합니다:
- 제목 (title)
- URL (url)
- 조회수 (views)
- 댓글수 (comments)
- 좋아요/추천수 (likes)
- 커뮤니티명 (community)
- 타임스탬프 (timestamp)
