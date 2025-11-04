import asyncio
import json
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from src.crawlers.fmkorea_crawler import FmkoreaCrawler


def ensure_outputs_dir() -> str:
    """outputs 디렉토리 생성"""
    out_dir = os.path.join(os.getcwd(), "outputs")
    os.makedirs(out_dir, exist_ok=True)
    return out_dir


async def main() -> None:
    """에펨코리아 크롤링 실행"""
    # MAX_POSTS 기본값: None (기간 내 모든 데이터 수집)
    max_posts_env = os.getenv("MAX_POSTS", "")
    max_posts = None  # 기본값: 기간 내 모든 데이터 수집
    if max_posts_env.strip():
        try:
            max_posts = int(max_posts_env)
            if max_posts == 0:  # 0으로 설정하면 전체 수집
                max_posts = None
        except Exception:
            max_posts = None  # 파싱 실패 시 None (전체 수집)

    async with FmkoreaCrawler() as crawler:
        results = await crawler.crawl(max_posts=max_posts)
        
        # Post 객체를 딕셔너리로 변환
        payload = []
        for p in results:
            item = p.model_dump()
            
            # created_at을 "2025-11-04 18:25" 형식으로 변환 (.을 -로 변환)
            if item.get("created_at"):
                if isinstance(item["created_at"], datetime):
                    item["created_at"] = item["created_at"].strftime('%Y-%m-%d %H:%M')
                elif isinstance(item["created_at"], str):
                    date_str = item["created_at"]
                    # "2025.11.04 18:25" 형식을 "2025-11-04 18:25" 형식으로 변환
                    if '.' in date_str and ' ' in date_str:
                        # 점을 하이픈으로 변환
                        date_str = date_str.replace('.', '-', 2)  # 처음 2개만 변환 (YYYY-MM-DD)
                        # 날짜와 시간 사이의 공백 처리
                        parts = date_str.split()
                        if len(parts) == 2:
                            date_part = parts[0]
                            time_part = parts[1]
                            # YYYY-MM-DD 형식 확인
                            if len(date_part.split('-')) == 3:
                                item["created_at"] = f"{date_part} {time_part}"
                            else:
                                # 파싱 시도
                                try:
                                    dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                                    item["created_at"] = dt.strftime('%Y-%m-%d %H:%M')
                                except:
                                    pass
                    else:
                        # ISO 형식이면 변환
                        try:
                            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                            item["created_at"] = dt.strftime('%Y-%m-%d %H:%M')
                        except:
                            pass
            
            # None 값을 기본값으로 설정
            if item.get("id") is None:
                item["id"] = ""
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

        # JSON 파일로 저장
        out_dir = ensure_outputs_dir()
        ts_name = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"fmkorea_popular_{ts_name}.json"
        fpath = os.path.join(out_dir, fname)
        
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        print(f"\n{'='*60}")
        print(f"✅ 크롤링 완료!")
        print(f"📁 저장 위치: {fpath}")
        print(f"📊 수집된 게시글 수: {len(payload)}개")
        print(f"{'='*60}\n")
        
        # 요약 출력
        if payload:
            print("📋 수집 요약:")
            print(f"  - 채널: {payload[0].get('channel', 'N/A')}")
            print(f"  - 제목 예시: {payload[0].get('title', 'N/A')[:50]}...")
            view_counts = [p.get('view_cnt', 0) for p in payload if p.get('view_cnt')]
            if view_counts:
                print(f"  - 조회수 범위: {min(view_counts)} ~ {max(view_counts)}")
            print(f"  - 롯데온 게시글: {sum(1 for p in payload if p.get('own_company') == 1)}개")


if __name__ == "__main__":
    asyncio.run(main())
