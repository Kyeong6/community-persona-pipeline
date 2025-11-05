"""
JSON 파일들을 CSV 형식으로 변환하여 community_data.csv에 추가하는 유틸리티
"""
import json
import os
import csv
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime


def get_last_id_and_existing_urls(csv_path: str) -> Tuple[int, set]:
    """기존 CSV 파일에서 마지막 id와 기존 URL들을 가져옴"""
    if not os.path.exists(csv_path):
        return 0, set()
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            last_id = 0
            existing_urls = set()
            
            for row in reader:
                try:
                    row_id = int(row.get('id', 0) or 0)
                    if row_id > last_id:
                        last_id = row_id
                except (ValueError, TypeError):
                    pass
                
                # 기존 URL 수집 (중복 체크용)
                url = row.get('url', '').strip()
                if url:
                    existing_urls.add(url)
            
            return last_id, existing_urls
    except Exception as e:
        print(f"⚠️ CSV 파일 읽기 오류: {e}")
        return 0, set()


def load_json_files(outputs_dir: str) -> List[Dict]:
    """outputs 디렉토리에서 모든 JSON 파일을 읽어서 합침"""
    all_posts = []
    json_files = sorted(Path(outputs_dir).glob("*.json"))
    
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    all_posts.extend(data)
                    print(f"📄 {json_file.name}: {len(data)}개 게시글 로드")
        except Exception as e:
            print(f"⚠️ {json_file.name} 읽기 오류: {e}")
            continue
    
    return all_posts


def convert_to_csv_format(posts: List[Dict], start_id: int, existing_urls: set[str] = None) -> List[Dict]:
    """JSON 형식의 게시글을 CSV 형식으로 변환하고 id 할당 (중복 제거)"""
    if existing_urls is None:
        existing_urls = set()
    
    csv_rows = []
    current_id = start_id
    skipped_count = 0
    
    for post in posts:
        url = post.get('url', '').strip()
        
        # 중복 체크: URL이 이미 CSV에 있으면 스킵
        if url and url in existing_urls:
            skipped_count += 1
            continue
        
        current_id += 1
        
        # CSV 형식에 맞게 변환
        csv_row = {
            'id': current_id,
            'channel': post.get('channel', ''),
            'category': post.get('category', ''),
            'title': post.get('title', ''),
            'content': post.get('content', ''),
            'view_cnt': post.get('view_cnt', 0) or 0,
            'like_cnt': post.get('like_cnt', 0) or 0,
            'comment_cnt': post.get('comment_cnt', 0) or 0,
            'created_at': post.get('created_at', ''),
            'own_company': post.get('own_company', 0) or 0,
            'url': url
        }
        
        csv_rows.append(csv_row)
        # 기존 URL 목록에 추가 (같은 배치 내 중복 방지)
        if url:
            existing_urls.add(url)
    
    if skipped_count > 0:
        print(f"⏭️  중복 제거: {skipped_count}개 게시글 스킵")
    
    return csv_rows


def append_to_csv(csv_path: str, rows: List[Dict], append_mode: bool = True):
    """CSV 파일에 데이터 추가 또는 새로 작성"""
    fieldnames = [
        'id', 'channel', 'category', 'title', 'content',
        'view_cnt', 'like_cnt', 'comment_cnt', 'created_at',
        'own_company', 'url'
    ]
    
    file_exists = os.path.exists(csv_path)
    
    mode = 'a' if append_mode and file_exists else 'w'
    newline = ''  # CSV writer는 newline='' 필요
    
    with open(csv_path, mode, encoding='utf-8', newline=newline) as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
        
        # 헤더는 파일이 없거나 새로 작성할 때만
        if mode == 'w' or not file_exists:
            writer.writeheader()
        
        # 데이터 작성
        for row in rows:
            writer.writerow(row)


def append_posts_to_csv(posts: List[Dict], csv_path: Optional[str] = None):
    """
    크롤링 결과를 바로 CSV 파일에 추가 (JSON 저장 없이)
    
    Args:
        posts: 크롤링으로 얻은 Post 딕셔너리 리스트
        csv_path: 출력할 CSV 파일 경로 (기본값: ./community_data.csv)
    """
    if csv_path is None:
        csv_path = os.path.join(os.getcwd(), "community_data.csv")
    
    if not posts:
        print("⚠️ 추가할 게시글이 없습니다.")
        return
    
    print(f"\n{'='*60}")
    print(f"📝 CSV 저장 시작...")
    print(f"📁 CSV 파일: {csv_path}")
    
    # 1. 기존 CSV에서 마지막 id와 기존 URL 목록 확인
    last_id, existing_urls = get_last_id_and_existing_urls(csv_path)
    print(f"📊 마지막 ID: {last_id}, 기존 게시글 수: {len(existing_urls)}개")
    
    # 2. CSV 형식으로 변환 (중복 제거)
    csv_rows = convert_to_csv_format(posts, last_id, existing_urls)
    
    if csv_rows:
        print(f"✅ {len(csv_rows)}개 게시글 변환 완료 (ID: {last_id + 1} ~ {last_id + len(csv_rows)})")
        
        # 3. CSV 파일에 저장
        append_to_csv(csv_path, csv_rows, append_mode=True)
        print(f"💾 CSV 파일 저장 완료: {csv_path}")
        print(f"📊 총 {len(csv_rows)}개 게시글 추가됨")
    else:
        print("⚠️ 추가할 새 게시글이 없습니다 (모두 중복)")
    
    print(f"{'='*60}\n")


def merge_json_to_csv(
    outputs_dir: Optional[str] = None,
    csv_path: Optional[str] = None,
    append: bool = True
):
    """
    JSON 파일들을 읽어서 CSV로 변환
    
    Args:
        outputs_dir: outputs 디렉토리 경로 (기본값: ./outputs)
        csv_path: 출력할 CSV 파일 경로 (기본값: ./community_data.csv)
        append: 기존 CSV에 추가할지 여부 (False면 새로 작성)
    """
    # 기본 경로 설정
    if outputs_dir is None:
        outputs_dir = os.path.join(os.getcwd(), "outputs")
    if csv_path is None:
        csv_path = os.path.join(os.getcwd(), "community_data.csv")
    
    print(f"🔄 JSON → CSV 변환 시작")
    print(f"📁 JSON 디렉토리: {outputs_dir}")
    print(f"📁 CSV 파일: {csv_path}")
    
    # 1. 기존 CSV에서 마지막 id와 기존 URL 목록 확인
    if append:
        last_id, existing_urls = get_last_id_and_existing_urls(csv_path)
        print(f"📊 마지막 ID: {last_id}, 기존 게시글 수: {len(existing_urls)}개")
    else:
        last_id = 0
        existing_urls = set()
        print(f"📊 새 파일 생성 (ID: 1부터 시작)")
    
    # 2. JSON 파일들 로드
    all_posts = load_json_files(outputs_dir)
    print(f"📦 총 {len(all_posts)}개 게시글 로드 완료")
    
    if not all_posts:
        print("⚠️ 변환할 데이터가 없습니다.")
        return
    
    # 3. CSV 형식으로 변환 (중복 제거)
    csv_rows = convert_to_csv_format(all_posts, last_id, existing_urls)
    
    if csv_rows:
        print(f"✅ {len(csv_rows)}개 게시글 변환 완료 (ID: {last_id + 1} ~ {last_id + len(csv_rows)})")
        
        # 4. CSV 파일에 저장
        append_to_csv(csv_path, csv_rows, append)
        print(f"💾 CSV 파일 저장 완료: {csv_path}")
        print(f"📊 총 {len(csv_rows)}개 게시글 추가됨")
    else:
        print("⚠️ 추가할 새 게시글이 없습니다 (모두 중복)")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="JSON 파일들을 CSV로 변환")
    parser.add_argument(
        "--outputs-dir",
        type=str,
        default=None,
        help="outputs 디렉토리 경로 (기본값: ./outputs)"
    )
    parser.add_argument(
        "--csv-path",
        type=str,
        default=None,
        help="출력할 CSV 파일 경로 (기본값: ./community_data.csv)"
    )
    parser.add_argument(
        "--new",
        action="store_true",
        help="기존 CSV를 덮어쓰고 새로 작성"
    )
    
    args = parser.parse_args()
    
    merge_json_to_csv(
        outputs_dir=args.outputs_dir,
        csv_path=args.csv_path,
        append=not args.new
    )

