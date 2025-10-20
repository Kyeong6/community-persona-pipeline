from abc import ABC, abstractmethod
from playwright.async_api import async_playwright
from src.models.post import Post
from typing import List, Dict, Optional
import os
import re
import httpx
from dotenv import load_dotenv

load_dotenv()

class BaseCrawler(ABC):
    def __init__(self):
        self.browser = None
        self.page = None
        self.playwright = None
        self.headless = os.getenv('BROWSER_HEADLESS', 'true').lower() == 'true'
        self.timeout = int(os.getenv('BROWSER_TIMEOUT', '30000'))
        self.delay = int(os.getenv('BROWSER_DELAY', '1000'))
        self.naver_cookies: Optional[Dict[str, str]] = None
    
    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)
        self.page = await self.browser.new_page()
        self.page.set_default_timeout(self.timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    @abstractmethod
    async def crawl(self, max_posts: int = 20) -> List[Post]:
        pass
    
    async def login_naver(self) -> Dict[str, str]:
        """네이버 로그인 후 쿠키 반환"""
        naver_id = os.getenv('NAVER_ID')
        naver_password = os.getenv('NAVER_PASSWORD')
        
        if not naver_id or not naver_password:
            raise Exception("네이버 로그인 정보가 환경변수에 설정되지 않았습니다.")
        
        print("🫛🔐 네이버 로그인 시도...")
        
        await self.page.goto("https://nid.naver.com/nidlogin.login", wait_until="load")
        await self.page.wait_for_timeout(3000)
        
        # 로그인 폼 확인
        id_input = self.page.locator("#id")
        pw_input = self.page.locator("#pw")
        
        if not (await id_input.is_visible() and await pw_input.is_visible()):
            raise Exception("🫛🔐 로그인 입력창이 표시되지 않음")
        
        # 아이디 입력
        await id_input.click()
        await self.page.wait_for_timeout(1000)
        await self.page.evaluate(f"document.getElementById('id').value = '{naver_id}';")
        
        # 비밀번호 입력
        await pw_input.click()
        await self.page.wait_for_timeout(1000)
        await self.page.evaluate(f"document.getElementById('pw').value = '{naver_password}';")
        await self.page.wait_for_timeout(1000)
        
        # 로그인 버튼 클릭
        login_button = self.page.locator("#log\\.login")
        
        if not await login_button.is_visible():
            raise Exception("🫛🔐 로그인 버튼이 표시되지 않음")
        
        if not await login_button.is_enabled():
            raise Exception("🫛🔐 로그인 버튼이 비활성화됨")
        
        before_url = self.page.url
        print(f"🫛🔐 로그인 버튼 클릭 중... (현재 URL: {before_url})")
        
        await login_button.click()
        await self.page.wait_for_timeout(5000)
        
        after_url = self.page.url
        print(f"🫛🔐 로그인 버튼 클릭 완료 (현재 URL: {after_url})")
        
        if "nid.naver.com" in after_url:
            await self.page.screenshot(path="login_error.png")
            raise Exception("🫛🔐 로그인 실패: 캡차가 활성화되었거나 정보가 틀림")
        
        print("🫛🔐 로그인 성공 ✅")
        
        # 쿠키 추출
        cookies = await self.page.context.cookies()
        cookie_dict = {cookie["name"]: cookie["value"] for cookie in cookies}
        
        return cookie_dict
    
    async def get_club_id(self, cafe_url: str) -> int:
        """카페 URL에서 club_id 추출"""
        print(f"🫛 카페 정보 가져오는 중: {cafe_url}")
        
        async with httpx.AsyncClient(cookies=self.naver_cookies) as client:
            response = await client.get(cafe_url)
            response.raise_for_status()
            
            match = re.search(r'var\s+g_sClubId\s*=\s*"(\d+)"', response.text)
            if not match:
                raise Exception("🫛❌ Club ID를 찾을 수 없음")
            
            club_id = int(match.group(1))
            print(f"🫛 Club ID: {club_id}")
            return club_id
    
    async def safe_click(self, selector: str) -> bool:
        """안전한 클릭 메서드"""
        try:
            await self.page.wait_for_selector(selector, timeout=5000)
            await self.page.click(selector)
            await self.page.wait_for_timeout(self.delay)
            return True
        except Exception as e:
            print(f"클릭 실패: {selector}, 오류: {e}")
            return False
    
    async def safe_get_text(self, selector: str) -> str:
        """안전한 텍스트 추출 메서드"""
        try:
            element = await self.page.wait_for_selector(selector, timeout=3000)
            return await element.inner_text() if element else ""
        except Exception:
            return ""
    
    async def safe_get_attribute(self, selector: str, attribute: str) -> str:
        """안전한 속성 추출 메서드"""
        try:
            element = await self.page.wait_for_selector(selector, timeout=3000)
            return await element.get_attribute(attribute) if element else ""
        except Exception:
            return ""
