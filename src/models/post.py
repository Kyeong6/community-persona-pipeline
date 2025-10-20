from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class Post(BaseModel):
    title: str
    url: str
    views: Optional[int] = None
    comments: Optional[int] = None
    likes: Optional[int] = None
    timestamp: Optional[datetime] = None
    community: str
