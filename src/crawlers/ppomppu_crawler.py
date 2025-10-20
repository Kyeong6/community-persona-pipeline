from src.crawlers.base_crawler import BaseCrawler
from src.models.post import Post
from typing import List
import re
from datetime import datetime

class PpomppuCrawler(BaseCrawler):
    def __init__(self):
        super().__init__()
        self.url = "https://www.ppomppu.co.kr/zboard/zboard.php?id=ppomppu&hotlist_flag=999"
        self.community = "뽐뿌"
    
    async def crawl(self, max_posts: int = 20) -> List[Post]:
        posts = []
        
        try:
            await self.page.goto(self.url)
            await self.page.wait_for_load_state('networkidle')
            
            # 게시글 목록 로드 대기
            await self.page.wait_for_selector('.list_table', timeout=10000)
            
            # 게시글 행들 추출
            post_rows = await self.page.query_selector_all('.list_table tr')
            
            for i, row in enumerate(post_rows[1:max_posts+1]):  # 헤더 제외
                try:
                    # 제목과 링크 추출
                    title_element = await row.query_selector('td.title a')
                    if not title_element:
                        continue
                    
                    title = await title_element.inner_text()
                    href = await title_element.get_attribute('href')
                    
                    if href and title:
                        # 조회수, 댓글수 추출 (목록에서)
                        views_element = await row.query_selector('td:nth-child(4)')
                        comments_element = await row.query_selector('td:nth-child(5)')
                        
                        views = 0
                        comments = 0
                        
                        if views_element:
                            views_text = await views_element.inner_text()
                            views = int(re.findall(r'\d+', views_text)[0]) if re.findall(r'\d+', views_text) else 0
                        
                        if comments_element:
                            comments_text = await comments_element.inner_text()
                            comments = int(re.findall(r'\d+', comments_text)[0]) if re.findall(r'\d+', comments_text) else 0
                        
                        # 게시글 상세 페이지로 이동하여 추천수 추출
                        await self.page.goto(f"https://www.ppomppu.co.kr/zboard/{href}")
                        await self.page.wait_for_load_state('networkidle')
                        
                        likes = await self._extract_likes()
                        
                        post = Post(
                            title=title.strip(),
                            url=f"https://www.ppomppu.co.kr/zboard/{href}",
                            views=views,
                            comments=comments,
                            likes=likes,
                            community=self.community,
                            timestamp=datetime.now()
                        )
                        posts.append(post)
                        
                        # 요청 간격 조절
                        await self.page.wait_for_timeout(1000)
                        
                except Exception as e:
                    print(f"게시글 {i+1} 처리 중 오류: {e}")
                    continue
                    
        except Exception as e:
            print(f"뽐뿌 크롤링 오류: {e}")
        
        return posts
    
    async def _extract_likes(self) -> int:
        """추천수 추출"""
        try:
            likes_text = await self.safe_get_text('.recommend_count')
            if likes_text:
                numbers = re.findall(r'\d+', likes_text)
                if numbers:
                    return int(numbers[0])
        except Exception:
            pass
        return 0
