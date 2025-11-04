from src.crawlers.base_crawler import BaseCrawler
from src.models.post import Post
from typing import List, Dict, Optional
import re
from datetime import datetime, timedelta


class PpomppuCrawler(BaseCrawler):
    def __init__(self):
        super().__init__()
        self.popular_url = "https://www.ppomppu.co.kr/zboard/zboard.php?id=ppomppu&hotlist_flag=999"
        self.channel = "ppomppu"
    
    async def crawl(self, max_posts: int = None) -> List[Post]:
        """뽐뿌 인기글 크롤링 (오늘 기준 일주일 전까지)"""
        posts = []
        
        try:
            # 1. 인기글 페이지 접속 (로그인 불필요)
            print(f"🫛 인기글 페이지 접속: {self.popular_url}")
            
            # 재시도 로직
            max_retries = 3
            for retry in range(max_retries):
                try:
                    # 페이지 접속
                    response = await self.page.goto(
                        self.popular_url, 
                        wait_until="load",
                        timeout=30000
                    )
                    if response:
                        print(f"🫛 페이지 응답 상태: {response.status}")
                        if response.status != 200:
                            raise Exception(f"HTTP 상태 코드 오류: {response.status}")
            
                    # 페이지 로딩 대기 (동적 콘텐츠 고려)
                    await self.page.wait_for_timeout(3000)
            
                    # 페이지 내용 확인
                    page_title = await self.page.title()
                    print(f"🫛 페이지 제목: {page_title[:50]}...")
                    
                    # 실제 HTML 구조 확인
                    page_content = await self.page.content()
                    print(f"🫛 페이지 길이: {len(page_content)} bytes")
                    
                    # 다양한 선택자로 테이블 찾기 시도
                    selectors_to_try = [
                        '.list_table',
                        'table.list_table',
                        '.board_table',
                        'table.board_table',
                        'table',
                        '[class*="list"]',
                        '[class*="table"]',
                        '[id*="list"]'
                    ]
                    
                    table_found = False
                    for selector in selectors_to_try:
                        try:
                            element = await self.page.query_selector(selector)
                            if element:
                                print(f"🫛 테이블 발견: {selector}")
                                # 게시글 행 확인
                                row_count = await self.page.evaluate(f"document.querySelectorAll('{selector} tr').length")
                                print(f"🫛 발견된 게시글 행 수: {row_count}")
                                if row_count > 0:
                                    table_found = True
                                    break
                        except:
                            continue
                    
                    if not table_found:
                        # 페이지 HTML 일부 출력 (디버깅)
                        body_text = await self.page.evaluate("document.body.innerText")
                        print(f"🫛 페이지 본문 일부: {body_text[:200]}...")
                        raise Exception(f"게시글 테이블을 찾을 수 없습니다. 페이지 구조 확인 필요.")
                    
                    break
                except Exception as e:
                    if retry < max_retries - 1:
                        print(f"🫛 페이지 로드 실패, 재시도 중... ({retry + 1}/{max_retries}): {e}")
                        await self.page.wait_for_timeout(5000)  # 재시도 전 대기 시간 증가
                    else:
                        print(f"🫛 페이지 로드 최종 실패: {e}")
                        import traceback
                        traceback.print_exc()
                        raise
            
            # 2. 게시글 목록 수집 (일주일 전까지 필터링, 번호 존재 여부 확인)
            post_items = await self._get_posts_from_popular_page(max_posts)
            print(f"🫛 수집된 게시글 목록: {len(post_items)}개")
            
            # 3. 각 게시글 상세 정보 수집
            for i, item in enumerate(post_items):
                try:
                    post_url = item.get('url', '')
                    comment_cnt = item.get('comment_cnt', 0)
                    title = item.get('title', '')
                    
                    print(f"🫛 게시글 데이터 수집 시작: {post_url} [{i+1}/{len(post_items)}]")
                    
                    # 게시글 상세 페이지 접속 (정적 페이지)
                    await self.page.goto(
                        post_url, 
                        wait_until="load",
                        timeout=30000
                    )
                    await self.page.wait_for_timeout(1000)
                        
                    # 게시글 데이터 추출
                    post = await self._extract_post_data(post_url, comment_cnt, title)
                    if post:
                        posts.append(post)
                        
                        # 요청 간격 조절
                        await self.page.wait_for_timeout(1000)
                        
                except Exception as e:
                    print(f"🫛 게시글 {post_url} 처리 중 오류: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
                    
        except Exception as e:
            print(f"🫛 뽐뿌 크롤링 오류: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"🫛 총 {len(posts)}개 게시글 수집 완료")
        return posts
    
    async def _get_posts_from_popular_page(self, max_posts: int = None) -> List[Dict]:
        """인기글 페이지에서 게시글 정보를 수집 (오늘 기준 일주일 전까지, 번호 존재 여부 확인)"""
        print(f"🫛 인기글 목록 수집 중...")
        
        # 날짜 필터: 오늘 기준 일주일 전
        today = datetime.now()
        week_ago = today - timedelta(days=7)
        print(f"🫛 날짜 필터: {week_ago.strftime('%Y-%m-%d')} ~ {today.strftime('%Y-%m-%d')}")
        
        collected_items: List[Dict] = []
        current_page = 1
        max_pages = 200  # 충분히 큰 값 (일주일 전까지 모든 페이지를 탐색)
        
        while current_page <= max_pages:
            # 현재 페이지에서 게시글 정보 추출
            await self.page.wait_for_timeout(2000)
            
            items = await self.page.evaluate("""
                (() => {
                    const items = [];
                    // 다양한 테이블 선택자 시도
                    let rows = [];
                    const selectors = [
                        '.list_table tr',
                        'table.list_table tr',
                        '.board_table tr',
                        'table.board_table tr',
                        'table tr',
                        '[class*="list"] tr',
                        '[class*="table"] tr'
                    ];
                    
                    for (const sel of selectors) {
                        rows = Array.from(document.querySelectorAll(sel));
                        if (rows.length > 0) {
                            console.log('테이블 발견:', sel, '행 수:', rows.length);
                            break;
                        }
                    }
                    
                    for (const row of rows) {
                        // 번호 컬럼 찾기 (첫 번째 td)
                        const noTd = row.querySelector('td:first-child');
                        if (!noTd) continue;
                        
                        const noText = noTd.innerText.trim();
                        // 번호가 존재하는지 확인 (공백, "-", "공지" 등 제외)
                        if (!noText || noText === '-' || noText === '공지' || isNaN(parseInt(noText))) {
                            continue;
                        }
                        
                        // 제목 링크 찾기
                        const titleLink = row.querySelector('td.title a, a[href*="view.php"]');
                        if (!titleLink) continue;
                        
                        const href = titleLink.getAttribute('href');
                        if (!href) continue;
                        
                        // URL 생성
                        let fullUrl = href;
                        if (href.startsWith('/')) {
                            fullUrl = 'https://www.ppomppu.co.kr' + href;
                        } else if (href.startsWith('view.php')) {
                            fullUrl = 'https://www.ppomppu.co.kr/zboard/' + href;
                        } else if (!href.startsWith('http')) {
                            fullUrl = 'https://www.ppomppu.co.kr/zboard/' + href;
                        }
                        
                        // 제목 추출
                        const titleText = titleLink.innerText.trim() || titleLink.textContent.trim();
                        
                        // 댓글수 추출 (제목 마지막 부분 또는 span.baseList-c)
                        let commentCount = 0;
                        const commentSpan = row.querySelector('span.baseList-c');
                        if (commentSpan) {
                            const commentText = commentSpan.innerText.trim();
                            const match = commentText.match(/(\\d+)/);
                            if (match) {
                                commentCount = parseInt(match[1]);
                            }
                        }
                        
                        // 제목에서도 댓글수 찾기 (제목 뒤 숫자 패턴)
                        if (commentCount === 0) {
                            // 제목 마지막 숫자 찾기 (예: "...7 [가전/전자]")
                            const titleMatch = titleText.match(/(\\d+)\\s*\\[[^\\]]+\\]$/);
                            if (titleMatch) {
                                commentCount = parseInt(titleMatch[1]);
                            }
                        }
                        
                        // 날짜 추출 (일반적으로 날짜 컬럼)
                        let dateText = '';
                        const dateCells = row.querySelectorAll('td');
                        for (const cell of dateCells) {
                            const text = cell.innerText.trim();
                            // 날짜 패턴 찾기 (YY/MM/DD 또는 HH:MM:SS)
                            if (text.match(/\\d{2}\\/\\d{2}\\/\\d{2}/) || text.match(/\\d{2}:\\d{2}:\\d{2}/)) {
                                dateText = text;
                                break;
                            }
                        }
                        
                        // 카테고리 추출 (제목에서 [카테고리] 패턴)
                        let category = '';
                        const categoryMatch = titleText.match(/^\\[([^\\]]+)\\]/);
                        if (categoryMatch) {
                            category = categoryMatch[1];
                        }
                        
                        items.push({
                            url: fullUrl,
                            title: titleText,
                            dateText: dateText,
                            comment_cnt: commentCount,
                            category: category,
                            no: noText
                        });
                    }
                    
                    return items;
                })()
            """)
            
            print(f"🫛 [페이지 {current_page}] 화면에서 발견된 게시글 수: {len(items)}")
            
            before_len = len(collected_items)
            found_old_posts = False  # 일주일 이전 게시글이 있는지 확인
            
            for item in items:
                url = item.get('url', '')
                title = item.get('title', '')
                date_text = item.get('dateText', '')
                
                # 날짜 필터링 (일주일 전까지)
                if date_text:
                    post_date = self._parse_date(date_text)
                    if post_date:
                        if post_date < week_ago:
                            print(f"🫛 제외: 일주일 이전 게시글 - {date_text}")
                            found_old_posts = True  # 일주일 이전 게시글이 발견됨
                            continue
                    else:
                        # 날짜 파싱 실패 시 제외 (명확한 날짜가 필요)
                        print(f"🫛 날짜 파싱 실패, 제외: {date_text}")
                        continue
                else:
                    # 날짜 정보가 없으면 제외
                    print(f"🫛 날짜 정보 없음, 제외")
                    continue
                
                # 중복 체크 (URL 기반)
                if url and url not in [item['url'] for item in collected_items]:
                    collected_items.append(item)
            
            after_len = len(collected_items)
            new_count = after_len - before_len
            print(f"🫛 [페이지 {current_page}] 신규 수집: {new_count}개, 누적: {after_len}개")
            
            # 일주일 이전 게시글만 나오면 종료
            if found_old_posts and new_count == 0:
                print(f"🫛 일주일 이전 게시글만 남아 수집 종료")
                break
            
            # max_posts 제한이 있으면 체크 (디버깅용)
            if max_posts and len(collected_items) >= max_posts:
                print(f"🫛 max_posts({max_posts})에 도달하여 수집 종료")
                break
            
            # 다음 페이지로 이동
            if current_page < max_pages:
                next_page_clicked = False
                try:
                    # 방법 1: 다음 페이지 번호 버튼 찾기 (div.bottom-list a.num)
                    next_page_num = current_page + 1
                    
                    # div.bottom-list 내부의 페이지 번호 버튼 찾기
                    next_page_button = await self.page.query_selector(f'div.bottom-list a.num:has-text("{next_page_num}")')
                    if not next_page_button:
                        # href로 찾기
                        next_page_button = await self.page.query_selector(f'div.bottom-list a.num[href*="page={next_page_num}"]')
                    if not next_page_button:
                        # 일반적으로 다음 페이지 번호 찾기
                        next_page_button = await self.page.query_selector(f'a.num:has-text("{next_page_num}")')
                    
                    if next_page_button:
                        await next_page_button.click()
                        next_page_clicked = True
                        print(f"🫛 페이지 {next_page_num} 버튼 클릭 성공")
                    
                    # 방법 2: class="next" 버튼 클릭 (10페이지 이후)
                    if not next_page_clicked:
                        next_button = await self.page.query_selector('div.bottom-list a.next, a.next')
                        if next_button:
                            # 비활성화 확인
                            is_disabled = await next_button.get_attribute('disabled')
                            if not is_disabled:
                                await next_button.click()
                                next_page_clicked = True
                                print(f"🫛 다음 버튼(next) 클릭 성공 - 페이지 {next_page_num} 표시 예정")
                    
                    if next_page_clicked:
                        await self.page.wait_for_timeout(3000)
                        # 페이지가 실제로 변경되었는지 확인
                        current_url = self.page.url
                        if 'page=' in current_url:
                            page_match = re.search(r'page=(\d+)', current_url)
                            if page_match:
                                current_page = int(page_match.group(1))
                                print(f"🫛 페이지 {current_page} 로드 완료 (URL 확인)")
                            else:
                                # URL에 페이지 번호가 없으면 활성 페이지 번호 확인
                                active_page = await self.page.evaluate("""
                                    (() => {
                                        const activeLink = document.querySelector('div.bottom-list a.num.on');
                                        if (activeLink) {
                                            return parseInt(activeLink.innerText.trim());
                                        }
                                        return null;
                                    })()
                                """)
                                if active_page:
                                    current_page = active_page
                                    print(f"🫛 페이지 {current_page} 로드 완료 (활성 페이지 확인)")
                                else:
                                    current_page += 1
                                    print(f"🫛 페이지 {current_page} 로드 완료 (추정)")
                        else:
                            # URL에 페이지 번호가 없으면 활성 페이지 번호 확인
                            active_page = await self.page.evaluate("""
                                (() => {
                                    const activeLink = document.querySelector('div.bottom-list a.num.on');
                                    if (activeLink) {
                                        return parseInt(activeLink.innerText.trim());
                                    }
                                    return null;
                                })()
                            """)
                            if active_page:
                                current_page = active_page
                                print(f"🫛 페이지 {current_page} 로드 완료 (활성 페이지 확인)")
                            else:
                                current_page += 1
                                print(f"🫛 페이지 {current_page} 로드 완료 (추정)")
                    else:
                        print(f"🫛❌ 다음 페이지 버튼을 찾지 못함. 수집 종료")
                        break
                        
                except Exception as e:
                    print(f"🫛❌ 페이지네이션 클릭 오류: {e}")
                    import traceback
                    traceback.print_exc()
                    break
            else:
                print(f"🫛 최대 페이지({max_pages})에 도달하여 수집 종료")
                break
        
        # max_posts 제한 적용
        if max_posts:
            post_items = collected_items[:max_posts]
        else:
            post_items = collected_items
        
        print(f"🫛 총 {len(post_items)}개 인기글 수집 완료 (총 {current_page}페이지 순회)")
        return post_items
    
    def _parse_date(self, date_text: str) -> Optional[datetime]:
        """날짜 텍스트를 datetime으로 변환 (목록 페이지용)"""
        if not date_text:
            return None
        
        try:
            # 형식 1: "23:08:03" (오늘 날짜 - 시간만 표시)
            if re.match(r'^\d{2}:\d{2}:\d{2}$', date_text.strip()):
                today = datetime.now()
                time_parts = date_text.strip().split(':')
                return today.replace(hour=int(time_parts[0]), minute=int(time_parts[1]), second=int(time_parts[2]), microsecond=0)
            
            # 형식 2: "25/11/02" (YY/MM/DD)
            if re.match(r'^\d{2}/\d{2}/\d{2}$', date_text.strip()):
                parts = date_text.strip().split('/')
                year = 2000 + int(parts[0])
                month = int(parts[1])
                day = int(parts[2])
                return datetime(year, month, day)
            
            # 형식 3: "2025-11-02 09:33" (YYYY-MM-DD HH:MM) - 상세 페이지 형식도 지원
            match = re.search(r'(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})', date_text)
            if match:
                year = int(match.group(1))
                month = int(match.group(2))
                day = int(match.group(3))
                hour = int(match.group(4))
                minute = int(match.group(5))
                return datetime(year, month, day, hour, minute)
            
            # 형식 4: "2025.11.02. 12:39" (YYYY.MM.DD. HH:MM)
            match = re.search(r'(\d{4})\.(\d{1,2})\.(\d{1,2})\.?\s*(\d{1,2}):(\d{1,2})', date_text)
            if match:
                year = int(match.group(1))
                month = int(match.group(2))
                day = int(match.group(3))
                hour = int(match.group(4))
                minute = int(match.group(5))
                return datetime(year, month, day, hour, minute)
            
        except Exception as e:
            print(f"🫛 날짜 파싱 오류: {date_text} - {e}")
            return None
        
        return None
    
    async def _extract_post_data(self, post_url: str, comment_cnt: int, title_from_list: str) -> Optional[Post]:
        """게시글 상세 페이지에서 데이터 추출"""
        try:
            # 제목 추출 (h1 태그에서 직접 텍스트 노드 추출)
            title = title_from_list
            # h1 태그를 우선적으로 찾기
            title_elem = await self.page.query_selector('h1')
            if not title_elem:
                # h1이 없으면 다른 선택자 시도
                title_elem = await self.page.query_selector('span.topTitle, .topTitle, [class*="title"]')
            
            if title_elem:
                # h1 태그인 경우: 이미지, 카테고리 span, 댓글 수 span 제외하고 텍스트만 추출
                if await title_elem.evaluate('el => el.tagName.toLowerCase() === "h1"'):
                    title_text = await title_elem.evaluate("""
                        (elem) => {
                            // 이미지, 카테고리 span, 댓글 수 span 제거
                            const clone = elem.cloneNode(true);
                            clone.querySelectorAll('img, span#comment, span[id*="comment"], span.subject_preface, span[class*="preface"], span[class*="subject"]').forEach(el => el.remove());
                            // 텍스트만 추출 (실제 제목 텍스트만)
                            return clone.innerText.trim();
                        }
                    """)
                    if title_text and title_text.strip():
                        title = title_text.strip()
                else:
                    # h1이 아닌 경우 기존 방식 사용
                    title_text = await title_elem.inner_text()
                    if title_text and title_text.strip():
                        title = title_text.strip()
            
            # 카테고리 추출 (원본 제목에서, h1에서 추출한 경우 카테고리 span에서 직접 추출)
            category = ''
            if title_elem and await title_elem.evaluate('el => el.tagName.toLowerCase() === "h1"'):
                # h1에서 카테고리 span 직접 추출
                category_text = await title_elem.evaluate("""
                    (elem) => {
                        const categorySpan = elem.querySelector('span.subject_preface, span[class*="preface"], span[class*="subject"]');
                        if (categorySpan) {
                            const text = categorySpan.innerText.trim();
                            // [네이버] 형식에서 네이버만 추출
                            const match = text.match(/\\[([^\\]]+)\\]/);
                            return match ? match[1] : text;
                        }
                        return '';
                    }
                """)
                if category_text:
                    category = category_text
            
            # 카테고리 추출 (fallback: 제목에서 패턴 매칭)
            if not category:
                category_match = re.search(r'^\[([^\]]+)\]', title)
                if category_match:
                    category = category_match.group(1)
            
            # 본문 내용 추출 (텍스트만, UI 요소 제외)
            content = ""
            content_selectors = [
                'table.board-contents',  # 더 정확한 선택자
                '.board-contents table',
                '.board-contents',
                '[class*="contents"]:not([class*="menu"]):not([class*="nav"])',
                '.view_content',
                '#article'
            ]
            
            # UI 관련 텍스트 목록 (본문이 아닌 것으로 판단)
            # 주의: 실제 본문에도 포함될 수 있는 일반적인 단어는 제외
            ui_keywords = [
                '뽐뿌', '이벤트', '정보', '커뮤니티', '갤러리', '장터', '포럼', '뉴스', '상담실',
                '로그인', '회원가입', '아이디비번찾기', '뽐뿌게시판', '사용기', '구매후기',
                '쿠폰게시판', '쇼핑포럼', '뽐뿌핫딜', '목록보기', '최신순', '작성순',
                '알림', '광고성 게시글', '에디터', 'HTML편집', '미리보기', '짤방',
                '업자신고', '다른의견', '이전글', '다음글', '등록일', '조회수', '추천하기',
                '질렀어요 신고', '첨부파일', '같이 보면 좋은 상품',  # '상품' 단독 제거, '같이 보면 좋은 상품'만
                '구매하셨다면', '후기를 남겨주세요', '구매후기 쓰기'
            ]
            
            for sel in content_selectors:
                try:
                    content_elem = await self.page.query_selector(sel)
                    if content_elem:
                        # UI 요소 제거하고 텍스트만 추출
                        content_text = await content_elem.evaluate("""
                            (elem) => {
                                const clone = elem.cloneNode(true);
                                
                                // 메뉴, 네비게이션, 사이드바 제거
                                clone.querySelectorAll('[class*="menu"], [class*="nav"], [class*="sidebar"], [id*="menu"], [id*="nav"], [id*="sidebar"]').forEach(el => el.remove());
                                
                                // 댓글 영역 제거
                                clone.querySelectorAll('[class*="comment"], [class*="reply"], [id*="comment"], [id*="reply"], [class*="reply_box"], [class*="comment_box"]').forEach(el => el.remove());
                                
                                // 추천하기, 다른의견, 질렀어요 신고, 첨부파일, 이전글/다음글 버튼 제거
                                clone.querySelectorAll('[class*="recommend"], [class*="like"], [class*="attach"], [class*="prev"], [class*="next"], [class*="list"]').forEach(el => el.remove());
                                
                                // "같이 보면 좋은 상품" 영역 제거 (정확한 문구로만)
                                const relatedProducts = Array.from(clone.querySelectorAll('*')).filter(el => {
                                    const text = el.innerText || el.textContent || '';
                                    // 정확히 "같이 보면 좋은 상품" 또는 유사한 패턴만 제거
                                    return text.includes('같이 보면 좋은') && (text.includes('상품') || text.includes('추천'));
                                });
                                relatedProducts.forEach(el => el.remove());
                                
                                // "구매하셨다면" 같은 안내 문구 제거
                                const guideTexts = Array.from(clone.querySelectorAll('*')).filter(el => {
                                    const text = el.innerText || el.textContent || '';
                                    return text.includes('구매하셨다면') || text.includes('후기를 남겨주세요') || text.includes('구매후기 쓰기');
                                });
                                guideTexts.forEach(el => el.remove());
                                
                                // 이미지 제거
                                clone.querySelectorAll('img').forEach(el => el.remove());
                                
                                // 링크는 제거하되 텍스트는 유지 (URL은 제거)
                                clone.querySelectorAll('a').forEach(link => {
                                    const href = link.getAttribute('href') || '';
                                    // URL 링크는 제거
                                    if (href.startsWith('http') || href.startsWith('//')) {
                                        link.remove();
                                    } else {
                                        // 상대 링크는 텍스트만 유지
                                        const textNode = document.createTextNode(link.innerText || link.textContent || '');
                                        link.parentNode.replaceChild(textNode, link);
                                    }
                                });
                                
                                return clone.innerText || clone.textContent || '';
                            }
                        """)
                        
                        if content_text:
                            # 줄바꿈 정리 (빈 줄 제거)
                            lines = [line.strip() for line in content_text.split('\n') if line.strip()]
                            
                            # 메타 정보 라인 제거 (등록일, 조회수, 추천 등)
                            filtered_lines = []
                            for line in lines:
                                # 메타 정보 패턴 제외
                                if (re.match(r'^(등록일|조회수|추천)\s*\d+', line) or
                                    re.match(r'^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}', line) or  # 날짜 패턴
                                    re.match(r'^https?://', line) or  # URL
                                    re.match(r'^\d+원$', line) or  # 가격만 있는 라인
                                    line in ['등록일', '조회수', '추천', '추천하기', '다른의견', '질렀어요 신고']):
                                    continue
                                filtered_lines.append(line)
                            
                            content = '\n'.join(filtered_lines)
                            
                            # UI 키워드가 많이 포함되어 있는지 확인 (정확한 매칭)
                            # 각 라인에서 UI 키워드가 포함되어 있는지 확인
                            ui_keyword_lines = 0
                            for line in filtered_lines:
                                for keyword in ui_keywords:
                                    if keyword in line:
                                        ui_keyword_lines += 1
                                        break  # 한 라인에서 하나의 키워드만 카운트
                            
                            total_lines = len(filtered_lines)
                            ui_ratio = ui_keyword_lines / max(total_lines, 1) if total_lines > 0 else 0
                            
                            # 실제 본문이 있는지 확인 (일정 길이 이상의 연속된 텍스트가 있는지)
                            has_meaningful_content = False
                            for line in filtered_lines:
                                # UI 키워드가 포함되지 않은 라인 중 길이가 충분한 라인이 있는지
                                is_ui_line = any(keyword in line for keyword in ui_keywords)
                                if not is_ui_line and len(line) > 20:  # 20자 이상의 의미있는 본문 라인
                                    has_meaningful_content = True
                                    break
                            
                            # UI 키워드 비율이 높고(50% 이상) 의미있는 본문이 없으면 본문 없는 것으로 판단
                            # 또는 UI 키워드 라인이 10개 이상이면 본문 없는 것으로 판단
                            if (ui_ratio >= 0.5 and not has_meaningful_content) or ui_keyword_lines >= 10:
                                print(f"🫛 UI 요소가 많이 포함되어 본문 없는 것으로 판단 (UI 키워드 라인: {ui_keyword_lines}개, 비율: {ui_ratio:.2f}, 의미있는 본문: {has_meaningful_content})")
                                content = ""  # 본문이 없는 것으로 처리
                                continue  # 다음 선택자 시도
                            
                            if len(content) > 10:
                                print(f"🫛 본문 추출 성공 (선택자: {sel}): {len(content)}자")
                                break
                except Exception as e:
                    continue
            
            # 조회수 추출 ("조회수" 텍스트 이후 값)
            view_cnt = 0
            try:
                page_text = await self.page.evaluate("document.body.innerText")
                view_match = re.search(r'조회수\s*[:：]?\s*([\d,]+)', page_text)
                if view_match:
                    view_num_str = view_match.group(1).replace(',', '')
                    view_cnt = int(view_num_str)
                    print(f"🫛 조회수 추출 성공: {view_match.group(1)} -> {view_cnt}")
            except Exception as e:
                pass
            
            # 좋아요 수 추출 (span.topTitle-rec em 태그 내 숫자)
            like_cnt = 0
            try:
                rec_span = await self.page.query_selector('span.topTitle-rec')
                if rec_span:
                    em_tag = await rec_span.query_selector('em')
                    if em_tag:
                        like_text = await em_tag.inner_text()
                        like_match = re.search(r'(\d+)', like_text)
                        if like_match:
                            like_cnt = int(like_match.group(1))
                            print(f"🫛 추천수 추출 성공: {like_text} -> {like_cnt}")
            except Exception as e:
                pass
            
            # 작성일시 추출 ("등록일" 이후 값) - ul.topTitle-mainbox li 요소에서 추출
            created_at = None
            try:
                # 방법 1: ul.topTitle-mainbox li 요소에서 "등록일 YYYY-MM-DD HH:MM" 형식 찾기
                mainbox = await self.page.query_selector('ul.topTitle-mainbox')
                if mainbox:
                    li_elements = await mainbox.query_selector_all('li')
                    for li in li_elements:
                        li_text = await li.inner_text()
                        # "등록일 2025-11-02 09:33" 형식 찾기
                        date_match = re.search(r'등록일\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})', li_text)
                        if date_match:
                            date_str = date_match.group(1).strip()
                            try:
                                created_at = datetime.strptime(date_str, '%Y-%m-%d %H:%M')
                                print(f"🫛 날짜 파싱 성공 (topTitle-mainbox): {date_str} -> {created_at}")
                                break
                            except:
                                continue
                
                # 방법 2: 페이지 텍스트에서 "등록일 YYYY-MM-DD HH:MM" 형식 찾기
                if not created_at:
                    page_text = await self.page.evaluate("document.body.innerText")
                    date_match = re.search(r'등록일\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})', page_text)
                    if date_match:
                        date_str = date_match.group(1).strip()
                        try:
                            created_at = datetime.strptime(date_str, '%Y-%m-%d %H:%M')
                            print(f"🫛 날짜 파싱 성공 (전체 텍스트): {date_str} -> {created_at}")
                        except:
                            pass
                
                # 방법 3: 기존 패턴 (YY/MM/DD 또는 HH:MM:SS) - 하위 호환성
                if not created_at:
                    page_text = await self.page.evaluate("document.body.innerText")
                    date_match = re.search(r'등록일[^\n]*[:：]?\s*(\d{2}/\d{2}/\d{2}|\d{2}:\d{2}:\d{2})', page_text)
                    if date_match:
                        date_text = date_match.group(1).strip()
                        created_at = self._parse_date(date_text)
                        if created_at:
                            print(f"🫛 날짜 파싱 성공 (기존 패턴): {date_text} -> {created_at}")
            except Exception as e:
                print(f"🫛 날짜 추출 오류: {e}")
            
            # URL 추출 (span.topTitle-copy 클릭하여 클립보드에서 가져오기)
            actual_url = post_url
            try:
                copy_span = await self.page.query_selector('span.topTitle-copy')
                if copy_span:
                    await copy_span.click()
                    await self.page.wait_for_timeout(500)
                    # 클립보드에서 URL 가져오기
                    clipboard_text = await self.page.evaluate("navigator.clipboard.readText()")
                    if clipboard_text and ('ppomppu.co.kr' in clipboard_text or 'view.php' in clipboard_text):
                        actual_url = clipboard_text
                        print(f"🫛 URL 클립보드 복사 성공: {actual_url}")
            except Exception as e:
                # 클립보드 접근 실패 시 원본 URL 사용
                pass
            
            # 게시글 ID 추출 (URL에서)
            article_id = None
            id_match = re.search(r'no=(\d+)', post_url)
            if id_match:
                article_id = int(id_match.group(1))
            
            # own_company: 제목에 "롯데온"이 있으면 1, 없으면 0
            own_company = 1 if title and '롯데온' in title else 0
            
            # content가 없거나 의미있는 내용이 없으면 None 반환 (pass)
            content_cleaned = content.strip() if content else ""
            if not content_cleaned or len(content_cleaned) < 10:
                print(f"🫛 content가 없어서 게시물 제외: {post_url}")
                return None
            
            print(f"🫛 추출 완료: title={title[:30]}..., view_cnt={view_cnt}, comment_cnt={comment_cnt}, like_cnt={like_cnt}")
            
            return Post(
                id=article_id,
                channel=self.channel,
                category="",  # category는 빈 문자열로 고정
                title=title.strip() if title else "",
                content=content_cleaned,
                view_cnt=view_cnt,
                like_cnt=like_cnt,
                comment_cnt=comment_cnt,
                created_at=created_at,
                own_company=own_company,
                url=actual_url
            )
                
        except Exception as e:
            print(f"🫛 게시글 데이터 추출 오류: {e}")
            import traceback
            traceback.print_exc()
            return None
