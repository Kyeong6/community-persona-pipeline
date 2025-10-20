from src.crawlers.base_crawler import BaseCrawler
from src.models.post import Post
from typing import List
import re
from datetime import datetime

class FmkoreaCrawler(BaseCrawler):
    def __init__(self):
        super().__init__()
        self.url = "https://www.fmkorea.com/index.php?mid=hotdeal&sort_index=pop&order_type=desc"
        self.community = "에펨코리아"
    
    async def crawl(self, max_posts: int = 20) -> List[Post]:
        posts = []
        
        try:
            await self.page.goto(self.url)
            await self.page.wait_for_load_state('networkidle')
            
            # 게시글 목록 로드 대기
            await self.page.wait_for_selector('.hotdeal_list', timeout=10000)
            
            # 스크롤하여 더 많은 게시글 로드
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await self.page.wait_for_timeout(2000)
            
            # 게시글 링크들 추출
            post_links = await self.page.query_selector_all('.hotdeal_list .title a')
            
            for i, link in enumerate(post_links[:max_posts]):
                try:
                    href = await link.get_attribute('href')
                    title = await link.inner_text()
                    
                    if href and title:
                        # 게시글 상세 페이지로 이동
                        await self.page.goto(f"https://www.fmkorea.com{href}")
                        await self.page.wait_for_load_state('networkidle')
                        
                        # 조회수, 댓글수, 추천수 추출
                        views = await self._extract_views()
                        comments = await self._extract_comments()
                        likes = await self._extract_likes()
                        
                        post = Post(
                            title=title.strip(),
                            url=f"https://www.fmkorea.com{href}",
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
            print(f"에펨코리아 크롤링 오류: {e}")
        
        return posts
    
    async def _extract_views(self) -> int:
        """조회수 추출"""
        try:
            views_text = await self.safe_get_text('.read_count')
            if views_text:
                numbers = re.findall(r'\d+', views_text)
                if numbers:
                    return int(numbers[0])
        except Exception:
            pass
        return 0
    
    async def _extract_comments(self) -> int:
        """댓글수 추출"""
        try:
            comments_text = await self.safe_get_text('.comment_count')
            if comments_text:
                numbers = re.findall(r'\d+', comments_text)
                if numbers:
                    return int(numbers[0])
        except Exception:
            pass
        return 0
    
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
