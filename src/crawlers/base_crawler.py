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
        # 브라우저 컨텍스트 옵션 설정
        context_options = {
            'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'viewport': {'width': 1920, 'height': 1080},
            'locale': 'ko-KR',
            'timezone_id': 'Asia/Seoul',
        }
        # headless 모드일 때 추가 옵션
        browser_options = {
            'headless': self.headless,
        }
        if not self.headless:
            browser_options['args'] = ['--disable-blink-features=AutomationControlled']
        
        self.browser = await self.playwright.chromium.launch(**browser_options)
        self.context = await self.browser.new_context(**context_options)
        self.page = await self.context.new_page()
        
        # 추가 헤더 설정
        await self.page.set_extra_http_headers({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
        })
        
        self.page.set_default_timeout(self.timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self, 'context') and self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    @abstractmethod
    async def crawl(self, max_posts: int = 20) -> List[Post]:
        pass
    
    async def login_naver(self) -> Dict[str, str]:
        """네이버 로그인 후 쿠키 반환"""
        # NAVER_COOKIE가 제공되면 로그인 과정을 우회한다.
        # 형식: "NAME=VALUE; NAME2=VALUE2"
        cookie_str = os.getenv('NAVER_COOKIE')
        if cookie_str:
            print("🫛🔐 NAVER_COOKIE 사용하여 로그인 우회 중...")
            cookie_dict: Dict[str, str] = {}
            for part in cookie_str.split(';'):
                part = part.strip()
                if not part or '=' not in part:
                    continue
                name, value = part.split('=', 1)
                cookie_dict[name.strip()] = value.strip()
            if not cookie_dict:
                raise Exception("🫛🔐 NAVER_COOKIE 파싱 실패: 값이 비어있음")
            self.naver_cookies = cookie_dict
            return cookie_dict

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
        # 1차: URL 경로에서 직접 파싱 시도 (예: https://cafe.naver.com/f-e/cafes/29434212/popular)
        direct = re.search(r"/cafes/(\d+)", cafe_url)
        if direct:
            club_id = int(direct.group(1))
            print(f"🫛 Club ID(직접 파싱): {club_id}")
            return club_id

        # 2차: 응답 HTML에서 g_sClubId 변수 파싱
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
