from src.crawlers.base_crawler import BaseCrawler
from src.models.post import Post
from typing import List, Dict, Optional
import re
from datetime import datetime, timedelta


class FmkoreaCrawler(BaseCrawler):
    def __init__(self):
        super().__init__()
        self.popular_url = "https://www.fmkorea.com/index.php?mid=hotdeal&sort_index=pop&order_type=desc"
        self.channel = "fmkorea"
    
    async def crawl(self, max_posts: int = None) -> List[Post]:
        """에펨코리아 인기글 크롤링 (오늘 기준 일주일 전까지)"""
        posts = []
        
        try:
            # 1. 인기글 페이지 접속
            print(f"🫛 인기글 페이지 접속: {self.popular_url}")
            
            # 재시도 로직
            max_retries = 3
            for retry in range(max_retries):
                try:
                    response = await self.page.goto(
                        self.popular_url,
                        wait_until="load",
                        timeout=30000
                    )
                    if response:
                        print(f"🫛 페이지 응답 상태: {response.status}")
                        if response.status != 200:
                            raise Exception(f"HTTP 상태 코드 오류: {response.status}")
                    
                    await self.page.wait_for_timeout(3000)
                    
                    # 페이지 내용 확인
                    page_title = await self.page.title()
                    print(f"🫛 페이지 제목: {page_title[:50]}...")
                    
                    break
                except Exception as e:
                    if retry < max_retries - 1:
                        print(f"🫛 페이지 로드 실패, 재시도 중... ({retry + 1}/{max_retries}): {e}")
                        await self.page.wait_for_timeout(5000)
                    else:
                        print(f"🫛 페이지 로드 최종 실패: {e}")
                        import traceback
                        traceback.print_exc()
                        raise
            
            # 2. 게시글 목록 수집 (일주일 전까지 필터링)
            post_items = await self._get_posts_from_popular_page(max_posts)
            print(f"🫛 수집된 게시글 목록: {len(post_items)}개")
            
            # 3. 각 게시글 상세 정보 수집
            for i, item in enumerate(post_items):
                try:
                    post_url = item.get('url', '')
                    title = item.get('title', '')
                    
                    print(f"🫛 게시글 데이터 수집 시작: {post_url} [{i+1}/{len(post_items)}]")
                    
                    # 게시글 상세 페이지 접속
                    await self.page.goto(
                        post_url,
                        wait_until="load",
                        timeout=30000
                    )
                    await self.page.wait_for_timeout(1000)
                    
                    # 게시글 데이터 추출
                    post = await self._extract_post_data(post_url, title)
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
            print(f"🫛 에펨코리아 크롤링 오류: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"🫛 총 {len(posts)}개 게시글 수집 완료")
        return posts
    
    async def _get_posts_from_popular_page(self, max_posts: int = None) -> List[Dict]:
        """인기글 페이지에서 게시글 정보를 수집 (오늘 기준 일주일 전까지)"""
        print(f"🫛 인기글 목록 수집 중...")
        
        # 날짜 필터: 오늘 기준 일주일 전
        today = datetime.now()
        week_ago = today - timedelta(days=7)
        print(f"🫛 날짜 필터: {week_ago.strftime('%Y-%m-%d')} ~ {today.strftime('%Y-%m-%d')}")
        
        collected_items: List[Dict] = []
        current_page = 1
        max_pages = 200  # 충분히 큰 값
        
        while current_page <= max_pages:
            await self.page.wait_for_timeout(2000)
            
            # 현재 페이지에서 게시글 정보 추출
            items = await self.page.evaluate("""
                (() => {
                    const items = [];
                    // 게시글 목록 찾기 (일반적으로 ul, li 또는 div 구조)
                    const articleSelectors = [
                        'ul.bd_lst li',
                        'li.li',
                        '.hotdeal_list li',
                        '[class*="list"] li',
                        'div[class*="article"]',
                        'tr[class*="list"]'
                    ];
                    
                    let rows = [];
                    for (const sel of articleSelectors) {
                        rows = Array.from(document.querySelectorAll(sel));
                        if (rows.length > 0) {
                            console.log('게시글 목록 발견:', sel, '개수:', rows.length);
                            break;
                        }
                    }
                    
                    for (const row of rows) {
                        // 제목 링크 찾기
                        const titleLink = row.querySelector('a[href*="/"], a[href*="index.php"]');
                        if (!titleLink) continue;
                        
                        const href = titleLink.getAttribute('href');
                        if (!href) continue;
                        
                        // URL 생성
                        let fullUrl = href;
                        if (href.startsWith('/')) {
                            fullUrl = 'https://www.fmkorea.com' + href;
                        } else if (!href.startsWith('http')) {
                            fullUrl = 'https://www.fmkorea.com/' + href;
                        }
                        
                        // 제목 추출
                        const titleText = titleLink.innerText.trim() || titleLink.textContent.trim();
                        if (!titleText) continue;
                        
                        // 날짜 추출 (span.date.m_no 또는 유사한 구조)
                        let dateText = '';
                        const dateElem = row.querySelector('span.date, .date, [class*="date"]');
                        if (dateElem) {
                            dateText = dateElem.innerText.trim();
                        }
                        
                        items.push({
                            url: fullUrl,
                            title: titleText,
                            dateText: dateText
                        });
                    }
                    
                    return items;
                })()
            """)
            
            print(f"🫛 [페이지 {current_page}] 화면에서 발견된 게시글 수: {len(items)}")
            
            before_len = len(collected_items)
            found_old_posts = False
            
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
                            found_old_posts = True
                            continue
                    else:
                        # 날짜 파싱 실패 시 제외
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
            
            # max_posts 제한이 있으면 체크
            if max_posts and len(collected_items) >= max_posts:
                print(f"🫛 max_posts({max_posts})에 도달하여 수집 종료")
                break
            
            # 다음 페이지로 이동
            if current_page < max_pages:
                next_page_clicked = False
                try:
                    next_page_num = current_page + 1
                    
                    # 방법 1: 페이지 번호 링크 찾기 (a[href*="page=X"])
                    next_page_button = await self.page.query_selector(f'a[href*="page={next_page_num}"]')
                    if not next_page_button:
                        # 방법 2: "다음" 버튼 찾기 (class="direction")
                        next_button = await self.page.query_selector('a.direction[href*="page="]')
                        if next_button:
                            # 다음 버튼의 href에서 페이지 번호 추출
                            next_href = await next_button.get_attribute('href')
                            if next_href:
                                page_match = re.search(r'page=(\d+)', next_href)
                                if page_match:
                                    next_page_num = int(page_match.group(1))
                                    next_page_button = next_button
                    
                    if next_page_button:
                        await next_page_button.click()
                        next_page_clicked = True
                        print(f"🫛 페이지 {next_page_num} 버튼 클릭 성공")
                    
                    if next_page_clicked:
                        await self.page.wait_for_timeout(3000)
                        # URL에서 현재 페이지 확인
                        current_url = self.page.url
                        if 'page=' in current_url:
                            page_match = re.search(r'page=(\d+)', current_url)
                            if page_match:
                                current_page = int(page_match.group(1))
                                print(f"🫛 페이지 {current_page} 로드 완료 (URL 확인)")
                            else:
                                current_page = next_page_num
                                print(f"🫛 페이지 {current_page} 로드 완료 (추정)")
                        else:
                            # URL에 페이지 번호가 없으면 활성 페이지 확인
                            active_page = await self.page.evaluate("""
                                (() => {
                                    const activeLink = document.querySelector('strong.this, a.this, .pagination a.on');
                                    if (activeLink) {
                                        const text = activeLink.innerText.trim();
                                        const num = parseInt(text);
                                        if (!isNaN(num)) {
                                            return num;
                                        }
                                    }
                                    return null;
                                })()
                            """)
                            if active_page:
                                current_page = active_page
                                print(f"🫛 페이지 {current_page} 로드 완료 (활성 페이지 확인)")
                            else:
                                current_page = next_page_num
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
        """날짜 텍스트를 datetime으로 변환"""
        if not date_text:
            return None
        
        try:
            date_text = date_text.strip()
            
            # 형식 1: "2025.11.04 18:25" (YYYY.MM.DD HH:MM)
            match = re.search(r'(\d{4})\.(\d{1,2})\.(\d{1,2})\s+(\d{1,2}):(\d{1,2})', date_text)
            if match:
                year = int(match.group(1))
                month = int(match.group(2))
                day = int(match.group(3))
                hour = int(match.group(4))
                minute = int(match.group(5))
                return datetime(year, month, day, hour, minute)
            
            # 형식 2: "2025-11-04 18:25" (YYYY-MM-DD HH:MM)
            match = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{1,2})', date_text)
            if match:
                year = int(match.group(1))
                month = int(match.group(2))
                day = int(match.group(3))
                hour = int(match.group(4))
                minute = int(match.group(5))
                return datetime(year, month, day, hour, minute)
            
            # 형식 3: "2025.11.03" (YYYY.MM.DD) - 날짜만, 시간 없음 (00:00으로 설정)
            match = re.match(r'^(\d{4})\.(\d{1,2})\.(\d{1,2})$', date_text)
            if match:
                year = int(match.group(1))
                month = int(match.group(2))
                day = int(match.group(3))
                return datetime(year, month, day, 0, 0)
            
            # 형식 4: "20:43", "20:12" (HH:MM) - 오늘 날짜로 가정
            match = re.match(r'^(\d{1,2}):(\d{1,2})$', date_text)
            if match:
                today = datetime.now()
                hour = int(match.group(1))
                minute = int(match.group(2))
                return today.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            # 형식 5: "11.04 18:25" (MM.DD HH:MM) - 올해로 가정
            match = re.search(r'(\d{1,2})\.(\d{1,2})\s+(\d{1,2}):(\d{1,2})', date_text)
            if match:
                today = datetime.now()
                month = int(match.group(1))
                day = int(match.group(2))
                hour = int(match.group(3))
                minute = int(match.group(4))
                return today.replace(month=month, day=day, hour=hour, minute=minute, second=0, microsecond=0)
            
        except Exception as e:
            print(f"🫛 날짜 파싱 오류: {date_text} - {e}")
            return None
        
        return None
    
    async def _extract_post_data(self, post_url: str, title_from_list: str) -> Optional[Post]:
        """게시글 상세 페이지에서 데이터 추출"""
        try:
            # 제목 추출 (h1.np_18px > span.np_18px_span)
            title = title_from_list
            title_elem = await self.page.query_selector('h1.np_18px span.np_18px_span')
            if not title_elem:
                # 대체 방법: h1.np_18px 또는 span.np_18px_span
                title_elem = await self.page.query_selector('h1.np_18px, span.np_18px_span')
            if title_elem:
                title_text = await title_elem.inner_text()
                if title_text and title_text.strip():
                    title = title_text.strip()
                    # 여러 줄일 경우 첫 번째 줄만
                    title = title.split('\n')[0].strip()
            
            # own_company: 제목에 "롯데온"이 있으면 1, 없으면 0
            own_company = 1 if title and '롯데온' in title else 0
            
            # 본문 내용 추출 (텍스트만, 이미지 제외, URL 및 탭 문자 제거)
            content = ""
            content_selectors = [
                '.rd_body',
                '.xe_content',
                '[class*="content"]',
                '[class*="body"]',
                '.document_content',
                'div[class*="article"]'
            ]
            
            for sel in content_selectors:
                try:
                    content_elem = await self.page.query_selector(sel)
                    if content_elem:
                        # 이미지와 링크 제외하고 텍스트만 추출
                        content = await content_elem.evaluate("""
                            (elem) => {
                                // 이미지와 링크 제거
                                const clone = elem.cloneNode(true);
                                clone.querySelectorAll('img, a.highslide').forEach(el => el.remove());
                                return clone.innerText.trim();
                            }
                        """)
                        if content:
                            # URL 제거 (https://www.fmkorea.com/숫자 패턴)
                            content = re.sub(r'https://www\.fmkorea\.com/\d+', '', content)
                            # "복사" 텍스트 제거
                            content = re.sub(r'복사\s*', '', content)
                            # 탭 문자(\t) 제거
                            content = content.replace('\t', ' ')
                            # 연속된 공백 정리
                            content = re.sub(r'\s+', ' ', content)
                            # 줄바꿈 정리
                            lines = [line.strip() for line in content.split('\n') if line.strip()]
                            content = '\n'.join(lines)
                            if len(content) > 10:
                                print(f"🫛 본문 추출 성공 (선택자: {sel}): {len(content)}자")
                                break
                except Exception as e:
                    continue
            
            # 조회수, 추천수, 댓글수 추출 (div.side.fr span b)
            view_cnt = 0
            like_cnt = 0
            comment_cnt = 0
            
            try:
                # div.side.fr 내부의 span 요소들 찾기
                side_div = await self.page.query_selector('div.side.fr')
                if side_div:
                    spans = await side_div.query_selector_all('span')
                    for span in spans:
                        span_text = await span.inner_text()
                        # "조회 수" 또는 "조회수" 패턴
                        if '조회' in span_text:
                            b_tag = await span.query_selector('b')
                            if b_tag:
                                view_text = await b_tag.inner_text()
                                view_match = re.search(r'([\d,]+)', view_text)
                                if view_match:
                                    view_cnt = int(view_match.group(1).replace(',', ''))
                                    print(f"🫛 조회수 추출 성공: {view_text} -> {view_cnt}")
                        # "추천 수" 또는 "추천수" 패턴
                        elif '추천' in span_text:
                            b_tag = await span.query_selector('b')
                            if b_tag:
                                like_text = await b_tag.inner_text()
                                like_match = re.search(r'([\d,]+)', like_text)
                                if like_match:
                                    like_cnt = int(like_match.group(1).replace(',', ''))
                                    print(f"🫛 추천수 추출 성공: {like_text} -> {like_cnt}")
                        # "댓글" 패턴
                        elif '댓글' in span_text:
                            b_tag = await span.query_selector('b')
                            if b_tag:
                                comment_text = await b_tag.inner_text()
                                comment_match = re.search(r'([\d,]+)', comment_text)
                                if comment_match:
                                    comment_cnt = int(comment_match.group(1).replace(',', ''))
                                    print(f"🫛 댓글수 추출 성공: {comment_text} -> {comment_cnt}")
            except Exception as e:
                print(f"🫛 통계 추출 오류: {e}")
            
            # 작성일시 추출 (span.date.m_no)
            created_at = None
            try:
                date_elem = await self.page.query_selector('span.date.m_no, .date.m_no')
                if date_elem:
                    date_text = await date_elem.inner_text()
                    if date_text:
                        created_at = self._parse_date(date_text)
                        if created_at:
                            print(f"🫛 날짜 파싱 성공: {date_text} -> {created_at}")
                
                # 대체 방법: div.top_area 내부에서 찾기
                if not created_at:
                    top_area = await self.page.query_selector('div.top_area')
                    if top_area:
                        date_elem = await top_area.query_selector('span.date, .date')
                        if date_elem:
                            date_text = await date_elem.inner_text()
                            if date_text:
                                created_at = self._parse_date(date_text)
                                if created_at:
                                    print(f"🫛 날짜 파싱 성공 (top_area): {date_text} -> {created_at}")
            except Exception as e:
                print(f"🫛 날짜 추출 오류: {e}")
            
            # URL 추출 (div.document_address a 또는 data-clipboard-text)
            actual_url = post_url
            try:
                # 방법 1: div.document_address a 태그
                doc_address = await self.page.query_selector('div.document_address')
                if doc_address:
                    a_tag = await doc_address.query_selector('a')
                    if a_tag:
                        url_text = await a_tag.inner_text()
                        if url_text and 'fmkorea.com' in url_text:
                            actual_url = url_text.strip()
                            print(f"🫛 URL 추출 성공 (document_address): {actual_url}")
                
                # 방법 2: data-clipboard-text 속성
                if actual_url == post_url:
                    copy_button = await self.page.query_selector('button[data-clipboard-text]')
                    if copy_button:
                        clipboard_url = await copy_button.get_attribute('data-clipboard-text')
                        if clipboard_url and 'fmkorea.com' in clipboard_url:
                            actual_url = clipboard_url
                            print(f"🫛 URL 추출 성공 (clipboard): {actual_url}")
            except Exception as e:
                print(f"🫛 URL 추출 오류: {e}")
            
            print(f"🫛 추출 완료: title={title[:30]}..., view_cnt={view_cnt}, comment_cnt={comment_cnt}, like_cnt={like_cnt}, own_company={own_company}")
            
            return Post(
                id=None,
                channel=self.channel,
                category="",
                title=title.strip() if title else "",
                content=content.strip() if content else "",
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
