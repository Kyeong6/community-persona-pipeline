from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class Post(BaseModel):
    id: Optional[int] = None
    channel: str
    category: Optional[str] = None
    title: str
    content: Optional[str] = None
    view_cnt: Optional[int] = None
    like_cnt: Optional[int] = None
    comment_cnt: Optional[int] = None
    created_at: Optional[datetime] = None
    own_company: int = 0
    url: str
    # 하위 호환성을 위한 필드
    views: Optional[int] = None
    comments: Optional[int] = None
    likes: Optional[int] = None
    timestamp: Optional[datetime] = None
    community: Optional[str] = None
    
    def __init__(self, **data):
        # 하위 호환성: views -> view_cnt, comments -> comment_cnt, likes -> like_cnt
        if 'views' in data and 'view_cnt' not in data:
            data['view_cnt'] = data['views']
        if 'comments' in data and 'comment_cnt' not in data:
            data['comment_cnt'] = data['comments']
        if 'likes' in data and 'like_cnt' not in data:
            data['like_cnt'] = data['likes']
        if 'timestamp' in data and 'created_at' not in data:
            data['created_at'] = data['timestamp']
        super().__init__(**data)
