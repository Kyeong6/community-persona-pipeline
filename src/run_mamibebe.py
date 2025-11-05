import asyncio
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from src.crawlers.mamibebe_crawler import MamibebeCrawler


async def main() -> None:
    """맘이베베 크롤링 실행"""
    max_posts_env = os.getenv("MAX_POSTS", "")
    max_posts = None
    if max_posts_env.strip():
        try:
            max_posts = int(max_posts_env)
        except Exception:
            max_posts = None

    async with MamibebeCrawler() as crawler:
        results = await crawler.crawl(max_posts=max_posts)
        
        # Post 객체를 딕셔너리로 변환
        payload = []
        for p in results:
            item = p.model_dump()
            
            # created_at을 "2025-11-02 12:39" 형식으로 변환
            if item.get("created_at"):
                if isinstance(item["created_at"], datetime):
                    item["created_at"] = item["created_at"].strftime('%Y-%m-%d %H:%M')
                elif isinstance(item["created_at"], str):
                    # 이미 문자열인 경우 그대로 사용 (ISO 형식이면 변환)
                    try:
                        dt = datetime.fromisoformat(item["created_at"].replace('Z', '+00:00'))
                        item["created_at"] = dt.strftime('%Y-%m-%d %H:%M')
                    except:
                        pass
            
            # None 값을 기본값으로 설정
            if item.get("category") is None:
                item["category"] = ""
            if item.get("content") is None:
                item["content"] = ""
            
            # 불필요한 속성 제거 (views, comments, likes, timestamp, community)
            item.pop("views", None)
            item.pop("comments", None)
            item.pop("likes", None)
            item.pop("timestamp", None)
            item.pop("community", None)
            
            payload.append(item)

        print(f"\n{'='*60}")
        print(f"✅ 크롤링 완료!")
        print(f"📊 수집된 게시글 수: {len(payload)}개")
        print(f"{'='*60}\n")
        
        # 요약 출력
        if payload:
            print("📋 수집 요약:")
            print(f"  - 채널: {payload[0].get('channel', 'N/A')}")
            print(f"  - 제목 예시: {payload[0].get('title', 'N/A')[:50]}...")
            print(f"  - 조회수 범위: {min(p.get('view_cnt', 0) for p in payload)} ~ {max(p.get('view_cnt', 0) for p in payload)}")
            print(f"  - 롯데온 게시글: {sum(1 for p in payload if p.get('own_company') == 1)}개")
        
        # CSV에 바로 저장
        if payload:
            from src.utils.json_to_csv import append_posts_to_csv
            append_posts_to_csv(payload)


if __name__ == "__main__":
    asyncio.run(main())

