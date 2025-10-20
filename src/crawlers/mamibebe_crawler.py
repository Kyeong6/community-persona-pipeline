from src.crawlers.base_crawler import BaseCrawler
from src.models.post import Post
from typing import List
import httpx
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class MamibebeCrawler(BaseCrawler):
    def __init__(self):
        super().__init__()
        self.cafe_url = os.getenv('NAVER_CAFE_URL', 'https://cafe.naver.com/f-e/cafes/29434212/popular')
        self.community = "맘이베베"
        self.club_id = None
    
    async def crawl(self, max_posts: int = 20) -> List[Post]:
        posts = []
        
        try:
            # 1. 네이버 로그인
            self.naver_cookies = await self.login_naver()
            
            # 2. Club ID 추출
            self.club_id = await self.get_club_id(self.cafe_url)
            
            # 3. 인기글 ID 목록 수집
            post_ids = await self._get_popular_post_ids(max_posts)
            
            # 4. 각 게시글 상세 정보 수집
            for i, post_id in enumerate(post_ids):
                try:
                    print(f"🫛 게시글 데이터 수집 중: {post_id} [{i+1}/{len(post_ids)}]")
                    
                    # 게시글 상세 정보
                    post_data = await self._get_post_data(post_id)
                    if not post_data:
                        continue
                    
                    # 댓글 및 좋아요 정보
                    extra_data = await self._get_post_extra_data(post_id)
                    
                    # Post 객체 생성
                    post = Post(
                        title=post_data["article"]["subject"],
                        url=f"https://cafe.naver.com/f-e/cafes/{self.club_id}/articles/{post_id}",
                        views=post_data["article"]["readCount"],
                        comments=post_data["article"]["commentCount"],
                        likes=len(extra_data.get("likeItUsers", [])) if extra_data else 0,
                        community=self.community,
                        timestamp=datetime.now()
                    )
                    posts.append(post)
                    
                    # 요청 간격 조절
                    await self.page.wait_for_timeout(1000)
                    
                except Exception as e:
                    print(f"게시글 {post_id} 처리 중 오류: {e}")
                    continue
                    
        except Exception as e:
            print(f"맘이베베 크롤링 오류: {e}")
        
        print(f"🫛 총 {len(posts)}개 게시글 수집 완료")
        return posts
    
    async def _get_popular_post_ids(self, max_posts: int) -> List[int]:
        """인기글 ID 목록 수집"""
        print(f"🫛 인기글 ID 목록 수집 중... (최대 {max_posts}개)")
        
        post_ids = []
        page_num = 1
        
        async with httpx.AsyncClient(cookies=self.naver_cookies) as client:
            while len(post_ids) < max_posts:
                try:
                    # 인기글 목록 API 호출
                    response = await client.get(
                        f"https://apis.naver.com/cafe-web/cafe-search-api/v1.0/cafes/{self.club_id}/search/articles",
                        params={
                            "query": "",  # 빈 쿼리로 전체 검색
                            "perPage": 15,
                            "page": page_num,
                            "views": "MEMBER_LEVEL,COUNT,SALE_INFO,CAFE_MENU",
                        }
                    )
                    response.raise_for_status()
                    data = response.json()
                    
                    result = data["result"]
                    article_list = result["articleList"]
                    
                    if not article_list:
                        break
                    
                    # 게시글 ID 추출
                    for article in article_list:
                        if len(post_ids) >= max_posts:
                            break
                        post_id = article["item"]["articleId"]
                        post_ids.append(post_id)
                    
                    # 페이지 정보 확인
                    page_info = result["pageInfo"]
                    if page_num >= page_info["lastNavigationPageNumber"]:
                        break
                    
                    page_num += 1
                    
                except Exception as e:
                    print(f"페이지 {page_num} 수집 중 오류: {e}")
                    break
        
        print(f"🫛 {len(post_ids)}개 인기글 ID 수집 완료")
        return post_ids[:max_posts]
    
    async def _get_post_data(self, post_id: int) -> dict:
        """게시글 상세 정보 수집"""
        try:
            async with httpx.AsyncClient(cookies=self.naver_cookies) as client:
                response = await client.get(
                    f"https://article.cafe.naver.com/gw/v4/cafes/{self.club_id}/articles/{post_id}"
                )
                
                if response.status_code == 403:
                    print(f"🫛❌ 게시글 {post_id} 접근 거부됨")
                    return None
                elif response.status_code != 200:
                    print(f"🫛❌ 게시글 {post_id} 상태 코드: {response.status_code}")
                    return None
                
                data = response.json()
                return data["result"]
                
        except Exception as e:
            print(f"게시글 {post_id} 데이터 수집 오류: {e}")
            return None
    
    async def _get_post_extra_data(self, post_id: int) -> dict:
        """게시글 댓글 및 좋아요 정보 수집"""
        try:
            async with httpx.AsyncClient(cookies=self.naver_cookies) as client:
                response = await client.get(
                    f"https://article.cafe.naver.com/gw/v4/cafes/{self.club_id}/articles/{post_id}/comments/pages/1"
                )
                response.raise_for_status()
                data = response.json()
                return data["result"]
                
        except Exception as e:
            print(f"게시글 {post_id} 추가 데이터 수집 오류: {e}")
            return None