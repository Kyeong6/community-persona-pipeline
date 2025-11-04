from src.crawlers.base_crawler import BaseCrawler
from src.models.post import Post
from typing import List, Set
import httpx
import os
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

class MamibebeCrawler(BaseCrawler):
    def __init__(self):
        super().__init__()
        self.cafe_main_url = "https://cafe.naver.com/skybluezw4rh"
        self.popular_url = "https://cafe.naver.com/f-e/cafes/29434212/popular"
        self.club_id = 29434212
        self.channel = "mam2bebe"
    
    async def crawl(self, max_posts: int = None) -> List[Post]:
        """맘이베베 인기글 크롤링 (오늘 기준 일주일 전까지)"""
        posts = []
        
        try:
            # 1. 네이버 로그인
            self.naver_cookies = await self.login_naver()
            
            # 2. 카페 입장
            print(f"🫛 카페 입장: {self.cafe_main_url}")
            await self.page.goto(self.cafe_main_url, wait_until="load")
            await self.page.wait_for_timeout(2000)
            
            # 3. 인기글 페이지 접속
            print(f"🫛 인기글 페이지 접속: {self.popular_url}")
            await self.page.goto(self.popular_url, wait_until="load")
            await self.page.wait_for_timeout(2000)
            
            # 4. 게시글 URL 목록 수집 (일주일 전까지 필터링)
            post_urls = await self._get_posts_from_popular_page(max_posts)
            print(f"🫛 수집된 게시글 URL: {len(post_urls)}개")
            
            # 5. 각 게시글 상세 정보 수집
            for i, post_url in enumerate(post_urls):
                try:
                    print(f"🫛 게시글 데이터 수집 시작: {post_url} [{i+1}/{len(post_urls)}]")
                    
                    # 게시글 상세 페이지 접속
                    await self.page.goto(post_url, wait_until="load")
                    await self.page.wait_for_timeout(2000)
                    
                    # 게시글 데이터 추출
                    post = await self._extract_post_data(post_url)
                    if post:
                        # 게시글 상세 페이지에서도 카카오페이 추천인 게시물 제외
                        title_normalized = post.title.strip() if post.title else ""
                        if '카카오페이' in title_normalized:
                            if '증권 추천인' in title_normalized or '피자만들기 추천인' in title_normalized:
                                print(f"🫛 제외: 카카오페이 추천인 게시물 (상세) - {title_normalized[:50]}")
                                continue
                        posts.append(post)
                    
                    # 요청 간격 조절
                    await self.page.wait_for_timeout(1000)
                    
                except Exception as e:
                    print(f"게시글 {post_url} 처리 중 오류: {e}")
                    continue
                    
        except Exception as e:
            print(f"맘이베베 크롤링 오류: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"🫛 총 {len(posts)}개 게시글 수집 완료")
        return posts
    
    async def _get_posts_from_popular_page(self, max_posts: int = None) -> List[str]:
        """인기글 페이지에서 게시글 URL을 수집 (오늘 기준 일주일 전까지)"""
        print(f"🫛 인기글 URL 목록 수집 중...")
        
        # 날짜 필터: 오늘 기준 일주일 전
        today = datetime.now()
        week_ago = today - timedelta(days=7)
        print(f"🫛 날짜 필터: {week_ago.strftime('%Y-%m-%d')} ~ {today.strftime('%Y-%m-%d')}")

        # 본문은 iframe#cafe_main 안에 로드됨
        try:
            iframe_elem = await self.page.wait_for_selector("iframe#cafe_main", timeout=10000)
            frame = await iframe_elem.content_frame()
        except Exception as e:
            print(f"🫛❌ 인기글 iframe 탐색 실패: {e}")
            frame = None

        if frame is None:
            print("🫛❌ iframe을 찾지 못해 URL 추출 불가")
            return []

        collected_urls: List[str] = []  # 순서 유지를 위해 리스트 사용
        current_page = 1
        max_pages = 12  # 최대 12페이지까지
        
        # 페이지네이션을 따라 모든 페이지 수집
        while current_page <= max_pages:
            print(f"🫛 [페이지 {current_page}] 게시글 수집 시작... 현재 {len(collected_urls)}개")
            
            # 현재 페이지에서 게시글 URL 추출
            items: List[dict] = await frame.evaluate(
                r"""
                (() => {
                  const items = [];
                  // 게시글 행이나 항목 찾기
                  const rows = Array.from(document.querySelectorAll('tr, li, .article_item, [class*="article"]'));
                  
                  for (const row of rows) {
                    const anchor = row.querySelector('a[href*="/articles/"], a[href*="skybluezw4rh"]');
                    if (!anchor) continue;
                    
                    const href = anchor.getAttribute('href');
                    if (!href) continue;
                    
                    // URL 패턴 매칭
                    const urlMatch = href.match(/(?:articles\/(\d+)|skybluezw4rh\/(\d+))/);
                    if (!urlMatch) continue;
                    
                    const articleId = urlMatch[1] || urlMatch[2];
                    if (!articleId) continue;
                    
                    // 제목 추출
                    const titleText = anchor.innerText.trim() || anchor.textContent.trim();
                    
                    // 날짜 정보 찾기
                    let dateText = '';
                    const dateEl = row.querySelector('.date, .time, [class*="date"], [class*="time"], td.date');
                    if (dateEl) dateText = dateEl.innerText.trim();
                    
                    // 전체 URL 생성
                    let fullUrl = href;
                    if (href.startsWith('/')) {
                      fullUrl = 'https://cafe.naver.com' + href;
                    } else if (href.includes('skybluezw4rh')) {
                      if (!href.startsWith('http')) {
                        fullUrl = 'https://cafe.naver.com/' + href;
                      }
                    }
                    
                    items.push({
                      url: fullUrl,
                      articleId: articleId,
                      title: titleText,
                      dateText: dateText
                    });
                  }
                  return items;
                })()
                """
            )
            print(f"🫛 [페이지 {current_page}] 화면에서 발견된 게시글 수: {len(items)}")

            before_len = len(collected_urls)
            for item in items:
                url = item.get('url', '')
                title = item.get('title', '')
                date_text = item.get('dateText', '')
                
                # 카카오페이 추천인 게시물 제외
                # 제목에서 공백 제거 후 정확히 매칭
                if title:
                    title_normalized = title.strip()
                    # "카카오페이 증권 추천인" 또는 "카카오페이 피자만들기 추천인" 포함 여부 확인
                    if '카카오페이' in title_normalized:
                        if '증권 추천인' in title_normalized or '피자만들기 추천인' in title_normalized:
                            print(f"🫛 제외: 카카오페이 추천인 게시물 - {title_normalized[:50]}")
                            continue
                
                # 날짜 필터링 (일주일 전까지)
                if date_text:
                    post_date = self._parse_date(date_text)
                    if post_date and post_date < week_ago:
                        continue  # 일주일 이전 게시글은 제외
                
                # 중복 체크 (URL 기반)
                if url and url not in collected_urls:
                    collected_urls.append(url)  # 순서 유지
                
                # max_posts 제한이 있으면 체크
                if max_posts and len(collected_urls) >= max_posts:
                    break

            after_len = len(collected_urls)
            new_count = after_len - before_len
            print(f"🫛 [페이지 {current_page}] 신규 수집: {new_count}개, 누적: {after_len}개")

            # max_posts에 도달하면 종료
            if max_posts and len(collected_urls) >= max_posts:
                print(f"🫛 max_posts({max_posts})에 도달하여 수집 종료")
                break

            # 다음 페이지로 이동
            if current_page < max_pages:
                next_page_clicked = False
                used_right_arrow = False  # '>' 버튼 사용 여부
                next_page_num = current_page + 1
                try:
                    # 먼저 다음 페이지 번호 버튼이 있는지 확인
                    next_page_num_exists = await frame.evaluate(f"""
                        (() => {{
                            const nextNum = {next_page_num};
                            const buttons = Array.from(document.querySelectorAll('a, button, span'));
                            for (const btn of buttons) {{
                                const text = btn.innerText.trim();
                                if (text === String(nextNum)) {{
                                    // 현재 페이지인지 확인 (활성화 상태면 스킵)
                                    const parent = btn.closest('div, li, span');
                                    if (parent && (parent.className.includes('active') || parent.className.includes('current'))) {{
                                        return false;
                                    }}
                                    // 클릭 가능한 요소인지 확인
                                    if (btn.style.display !== 'none' && btn.offsetParent !== null) {{
                                        return true;
                                    }}
                                }}
                            }}
                            return false;
                        }})()
                    """)
                    
                    # 방법 1: 다음 페이지 번호 버튼이 있으면 클릭
                    if next_page_num_exists:
                        clicked = await frame.evaluate(f"""
                            (() => {{
                                const nextNum = {next_page_num};
                                const buttons = Array.from(document.querySelectorAll('a, button'));
                                for (const btn of buttons) {{
                                    const text = btn.innerText.trim();
                                    if (text === String(nextNum)) {{
                                        const parent = btn.closest('div, li, span');
                                        if (parent && (parent.className.includes('active') || parent.className.includes('current'))) {{
                                            continue;
                                        }}
                                        if (btn.style.display !== 'none' && btn.offsetParent !== null) {{
                                            btn.click();
                                            return true;
                                        }}
                                    }}
                                }}
                                return false;
                            }})()
                        """)
                        if clicked:
                            next_page_clicked = True
                            print(f"🫛 페이지 {next_page_num} 버튼 클릭 성공")
                    
                    # 방법 2: 다음 페이지 번호가 없으면 '다음' 버튼 클릭 (10페이지 이후)
                    if not next_page_clicked:
                        # 방법 2-1: button.type_next 클래스 찾기
                        next_button_clicked = await frame.evaluate("""
                            (() => {
                                // class="btn type_next" 버튼 찾기
                                const buttons = Array.from(document.querySelectorAll('button.type_next, button[class*="type_next"], .type_next'));
                                for (const btn of buttons) {
                                    // 비활성화 상태 확인
                                    if (btn.disabled || btn.className.includes('disabled')) {
                                        continue;
                                    }
                                    // 클릭 가능한 요소인지 확인
                                    if (btn.style.display !== 'none' && btn.offsetParent !== null) {
                                        btn.click();
                                        return true;
                                    }
                                }
                                return false;
                            })()
                        """)
                        if next_button_clicked:
                            next_page_clicked = True
                            used_right_arrow = True
                            print(f"🫛 다음 버튼(type_next) 클릭 성공 - 페이지 {next_page_num} 표시 예정")
                        
                        # 방법 2-2: aria-label="다음" 또는 SVG 내 aria-label="다음" 찾기
                        if not next_page_clicked:
                            aria_next_clicked = await frame.evaluate("""
                                (() => {
                                    // aria-label="다음"이 있는 버튼 또는 SVG 찾기
                                    const buttons = Array.from(document.querySelectorAll('button, a'));
                                    for (const btn of buttons) {
                                        // 버튼 자체에 aria-label이 있거나
                                        if (btn.getAttribute('aria-label') === '다음') {
                                            if (!btn.disabled && btn.style.display !== 'none' && btn.offsetParent !== null) {
                                                btn.click();
                                                return true;
                                            }
                                        }
                                        // 버튼 내부의 SVG에 aria-label="다음"이 있는 경우
                                        const svg = btn.querySelector('svg[aria-label="다음"]');
                                        if (svg) {
                                            if (!btn.disabled && btn.style.display !== 'none' && btn.offsetParent !== null) {
                                                btn.click();
                                                return true;
                                            }
                                        }
                                    }
                                    return false;
                                })()
                            """)
                            if aria_next_clicked:
                                next_page_clicked = True
                                used_right_arrow = True
                                print(f"🫛 다음 버튼(aria-label) 클릭 성공 - 페이지 {next_page_num} 표시 예정")
                        
                        # 방법 2-3: '>' 텍스트 버튼 찾기 (fallback)
                        if not next_page_clicked:
                            right_arrow_clicked = await frame.evaluate("""
                                (() => {
                                    // '>' 버튼 찾기 (단일 화살표)
                                    const buttons = Array.from(document.querySelectorAll('a, button'));
                                    for (const btn of buttons) {
                                        const text = btn.innerText.trim();
                                        // 정확히 '>' 문자만 있는 버튼 찾기 (>>는 제외)
                                        if (text === '>') {
                                            // 비활성화 상태 확인
                                            if (btn.disabled || btn.className.includes('disabled')) {
                                                continue;
                                            }
                                            // 클릭 가능한 요소인지 확인
                                            if (btn.style.display !== 'none' && btn.offsetParent !== null) {
                                                btn.click();
                                                return true;
                                            }
                                        }
                                    }
                                    return false;
                                })()
                            """)
                            if right_arrow_clicked:
                                next_page_clicked = True
                                used_right_arrow = True
                                print(f"🫛 다음 페이지 버튼(>) 클릭 성공 - 페이지 {next_page_num} 표시 예정")
                    
                    if next_page_clicked:
                        # 페이지 로드 대기
                        await self.page.wait_for_timeout(3000)
                        # iframe 재참조 (페이지 전환 후)
                        try:
                            iframe_elem = await self.page.wait_for_selector("iframe#cafe_main", timeout=5000)
                            frame = await iframe_elem.content_frame()
                            
                            # '>' 버튼을 클릭한 경우, 다음에 나타나는 페이지 번호를 확인
                            if used_right_arrow:
                                # 페이지네이션이 업데이트되었는지 확인하고 현재 페이지 번호 추출
                                await self.page.wait_for_timeout(1000)
                                # 활성화된 페이지 번호 찾기
                                active_page = await frame.evaluate("""
                                    (() => {
                                        const buttons = Array.from(document.querySelectorAll('a, button, span'));
                                        for (const btn of buttons) {
                                            const parent = btn.closest('div, li, span');
                                            if (parent && (parent.className.includes('active') || parent.className.includes('current'))) {
                                                const text = btn.innerText.trim();
                                                const num = parseInt(text);
                                                if (!isNaN(num)) {
                                                    return num;
                                                }
                                            }
                                        }
                                        return null;
                                    })()
                                """)
                                if active_page:
                                    current_page = active_page
                                    print(f"🫛 페이지 {current_page} 로드 완료 (활성 페이지 감지)")
                                else:
                                    current_page += 1
                                    print(f"🫛 페이지 {current_page} 로드 완료 (추정)")
                            else:
                                current_page += 1
                                print(f"🫛 페이지 {current_page} 로드 완료")
                        except Exception as e:
                            print(f"🫛❌ 페이지 {next_page_num} 로드 실패: {e}")
                            break
                    else:
                        print(f"🫛❌ 페이지 {next_page_num} 버튼을 찾지 못함. 수집 종료")
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
            post_urls = collected_urls[:max_posts]
        else:
            post_urls = collected_urls
        print(f"🫛 총 {len(post_urls)}개 인기글 URL 수집 완료 (총 {current_page}페이지 순회)")
        return post_urls
    
    def _parse_date(self, date_text: str) -> datetime:
        """날짜 텍스트를 datetime으로 파싱"""
        if not date_text:
            return None
        
        try:
            date_text = date_text.strip()
            
            # "2025.11.02. 12:39" 형식 (날짜와 시간 모두 포함)
            datetime_match = re.match(r'(\d{4})\.(\d{1,2})\.(\d{1,2})\.?\s*(\d{1,2}):(\d{1,2})', date_text)
            if datetime_match:
                year, month, day, hour, minute = datetime_match.groups()
                return datetime(int(year), int(month), int(day), int(hour), int(minute))
            
            # "2025.11.02" 형식 (날짜만)
            date_only_match = re.match(r'(\d{4})\.(\d{1,2})\.(\d{1,2})', date_text)
            if date_only_match:
                year, month, day = date_only_match.groups()
                return datetime(int(year), int(month), int(day))
            
            # "10.14" 형식 (올해 가정)
            if re.match(r'\d{1,2}\.\d{1,2}', date_text):
                today = datetime.now()
                parts = date_text.split('.')
                return datetime(today.year, int(parts[0]), int(parts[1]))
            
            # "10-14" 형식
            if re.match(r'\d{1,2}-\d{1,2}', date_text):
                today = datetime.now()
                parts = date_text.split('-')
                return datetime(today.year, int(parts[0]), int(parts[1]))
            
            # "어제", "오늘" 등의 텍스트
            if '오늘' in date_text or 'today' in date_text.lower():
                return datetime.now()
            if '어제' in date_text or 'yesterday' in date_text.lower():
                return datetime.now() - timedelta(days=1)
                
        except Exception as e:
            print(f"🫛 날짜 파싱 오류: {date_text}, {e}")
            pass
        return None
    
    def _format_datetime(self, dt: datetime) -> str:
        """datetime을 "2025-11-02 12:39" 형식으로 변환"""
        if not dt:
            return None
        return dt.strftime('%Y-%m-%d %H:%M')
    
    async def _extract_post_data(self, post_url: str) -> Post:
        """게시글 상세 페이지에서 데이터 추출"""
        try:
            # iframe 내부 접근
            try:
                iframe_elem = await self.page.wait_for_selector("iframe#cafe_main", timeout=5000)
                frame = await iframe_elem.content_frame()
            except:
                frame = self.page
            
            # 게시글 ID 추출
            article_id_match = re.search(r'skybluezw4rh/(\d+)', post_url)
            article_id = int(article_id_match.group(1)) if article_id_match else None
            
            # 제목 추출
            title = ""
            title_selectors = [
                'h3.title_text',
                '.title_text',
                'h3[class*="title"]',
                '.ArticleTitle',
                'h3'
            ]
            for sel in title_selectors:
                try:
                    title_elem = await frame.query_selector(sel) if frame else await self.page.query_selector(sel)
                    if title_elem:
                        title = await title_elem.inner_text()
                        if title:
                            break
                except:
                    continue
            
            # 카테고리 추출 (카테고리명이 있으면)
            category = None
            category_selectors = [
                '.category',
                '[class*="category"]',
                '.board_name',
                '.menu_name'
            ]
            for sel in category_selectors:
                try:
                    cat_elem = await frame.query_selector(sel) if frame else await self.page.query_selector(sel)
                    if cat_elem:
                        category = await cat_elem.inner_text()
                        if category:
                            break
                except:
                    continue
            
            # 본문 내용 추출 (텍스트만, 이미지/링크 제외, 줄바꿈 유지)
            content = ""
            content_selectors = [
                '.se-main-container',
                '.article_container',
                'div.article_container',
                '.article_body',
                '[class*="article_container"]',
                '[class*="article"] [class*="body"]',
                '.ContentRenderer',
                '.article_viewer'
            ]
            
            # 방법 1: 가장 간단한 방법 - innerText 직접 사용
            for sel in content_selectors:
                try:
                    content_elem = await frame.query_selector(sel) if frame else await self.page.query_selector(sel)
                    if content_elem:
                        # innerText는 이미 텍스트만 추출함 (이미지/링크 제외)
                        content = await content_elem.inner_text()
                        if content:
                            # 줄바꿈 정리 (빈 줄 제거)
                            lines = [line.strip() for line in content.split('\n') if line.strip()]
                            content = '\n'.join(lines)
                            if len(content) > 10:  # 의미있는 길이인지 확인
                                print(f"🫛 본문 추출 성공 (선택자: {sel}): {len(content)}자")
                                break
                except Exception as e:
                    continue
            
            # 방법 2: frame에서 직접 추출 시도 (innerText로)
            if not content and frame:
                try:
                    # 가장 일반적인 선택자부터 시도
                    containers = await frame.query_selector_all('.se-main-container, .article_container, [class*="article_container"]')
                    for container in containers:
                        try:
                            content = await container.inner_text()
                            if content:
                                lines = [line.strip() for line in content.split('\n') if line.strip()]
                                content = '\n'.join(lines)
                                if len(content) > 10:
                                    print(f"🫛 본문 추출 성공 (iframe 직접): {len(content)}자")
                                    break
                        except:
                            continue
                except Exception as e:
                    print(f"🫛 본문 추출 오류 (iframe): {e}")
            
            # 조회수 추출 ("조회 3,907" 형식)
            view_cnt = 0
            view_selectors = [
                'span.count',  # 이미지에서 확인된 선택자
                '.count',
                '[class*="count"]',
                'span[class*="view"]',
                '[class*="view"]',
                '[class*="read"]'
            ]
            for sel in view_selectors:
                try:
                    view_elem = await frame.query_selector(sel) if frame else await self.page.query_selector(sel)
                    if view_elem:
                        view_text = await view_elem.inner_text()
                        # "조회 3,907" 형식에서 숫자 추출 (쉼표 포함 가능)
                        view_match = re.search(r'조회\s*([\d,]+)', view_text)
                        if view_match:
                            # 쉼표 제거 후 숫자로 변환
                            view_num_str = view_match.group(1).replace(',', '')
                            view_cnt = int(view_num_str)
                            print(f"🫛 조회수 추출 성공: {view_text} -> {view_cnt}")
                            break
                except Exception as e:
                    continue
            
            # 조회수를 찾지 못한 경우 페이지 전체에서 검색
            if view_cnt == 0:
                try:
                    page_text = await (frame.evaluate("document.body.innerText") if frame else self.page.evaluate("document.body.innerText"))
                    view_match = re.search(r'조회\s*([\d,]+)', page_text)
                    if view_match:
                        view_num_str = view_match.group(1).replace(',', '')
                        view_cnt = int(view_num_str)
                        print(f"🫛 전체 검색으로 조회수 찾음: {view_match.group(1)} -> {view_cnt}")
                except:
                    pass
            
            # 좋아요 수 추출
            like_cnt = 0
            like_selectors = [
                '[class*="like"]',
                '[class*="recommend"]',
                '.LikeButton',
                'text=/좋아요\\s*\\d+/'
            ]
            for sel in like_selectors:
                try:
                    like_elem = await frame.query_selector(sel) if frame else await self.page.query_selector(sel)
                    if like_elem:
                        like_text = await like_elem.inner_text()
                        like_match = re.search(r'(\d+)', like_text)
                        if like_match:
                            like_cnt = int(like_match.group(1))
                            break
                except:
                    continue
            
            # 댓글 수 추출
            comment_cnt = 0
            comment_selectors = [
                '[class*="comment"]',
                '[class*="reply"]',
                '.CommentButton',
                'text=/댓글\\s*\\d+/'
            ]
            for sel in comment_selectors:
                try:
                    comment_elem = await frame.query_selector(sel) if frame else await self.page.query_selector(sel)
                    if comment_elem:
                        comment_text = await comment_elem.inner_text()
                        comment_match = re.search(r'(\d+)', comment_text)
                        if comment_match:
                            comment_cnt = int(comment_match.group(1))
                            break
                except:
                    continue
            
            # 작성일시 추출 ("2025.11.02. 12:39" 형식)
            created_at = None
            date_selectors = [
                '.date',
                '[class*="date"]',
                '[class*="time"]',
                '.ArticleDate',
                '.article_info .date',
                '.article_info .time'
            ]
            for sel in date_selectors:
                try:
                    date_elem = await frame.query_selector(sel) if frame else await self.page.query_selector(sel)
                    if date_elem:
                        date_text = await date_elem.inner_text()
                        if date_text:
                            created_at = self._parse_date(date_text)
                            if created_at:
                                print(f"🫛 날짜 파싱 성공: {date_text} -> {created_at}")
                                break
                except Exception as e:
                    continue
            
            # 날짜를 찾지 못했을 경우 페이지 전체에서 검색
            if not created_at:
                try:
                    page_text = await (frame.evaluate("document.body.innerText") if frame else self.page.evaluate("document.body.innerText"))
                    date_match = re.search(r'(\d{4}\.\d{1,2}\.\d{1,2}\.?\s*\d{1,2}:\d{1,2})', page_text)
                    if date_match:
                        created_at = self._parse_date(date_match.group(1))
                        if created_at:
                            print(f"🫛 전체 검색으로 날짜 찾음: {date_match.group(1)} -> {created_at}")
                except:
                    pass
            
            # URL 복사 버튼 클릭하여 실제 URL 가져오기
            actual_url = post_url
            try:
                copy_btn = await frame.query_selector('button[class*="copy"], button[aria-label*="복사"], .copy_url') if frame else await self.page.query_selector('button[class*="copy"], button[aria-label*="복사"], .copy_url')
                if copy_btn:
                    await copy_btn.click()
                    await self.page.wait_for_timeout(500)
                    # 클립보드에서 URL 가져오기
                    clipboard_text = await self.page.evaluate("navigator.clipboard.readText()")
                    if clipboard_text and 'skybluezw4rh' in clipboard_text:
                        actual_url = clipboard_text
            except:
                pass
            
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
                channel=self.channel,  # "mam2bebe" 고정
                category=category,
                title=title.strip() if title else "",
                content=content_cleaned,
                view_cnt=view_cnt,
                like_cnt=like_cnt,
                comment_cnt=comment_cnt,
                created_at=created_at,
                own_company=own_company,  # 제목에 "롯데온" 포함 여부
                url=actual_url
            )
                
        except Exception as e:
            print(f"게시글 데이터 추출 오류: {e}")
            import traceback
            traceback.print_exc()
            return None
