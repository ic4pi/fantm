from datetime import datetime, timezone
from typing import Optional, List, Annotated, Any
from bson import ObjectId
from pydantic import BaseModel, BeforeValidator, Field, ConfigDict


def validate_object_id(v: Any) -> str:
    if isinstance(v, ObjectId):
        return str(v)
    if isinstance(v, str) and ObjectId.is_valid(v):
        return v
    raise ValueError("Invalid ObjectId")


PyObjectId = Annotated[str, BeforeValidator(validate_object_id)]


class BaseDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)
    id: Optional[PyObjectId] = Field(default=None, alias="_id")

    @classmethod
    def from_mongo(cls, doc: Optional[dict]):
        if doc is None:
            return None
        return cls(**doc)

    def to_mongo(self) -> dict:
        data = self.model_dump(by_alias=True, exclude_none=True)
        data.pop("_id", None)
        return data


class Character(BaseModel):
    name: str
    role: str = ""
    description: str = ""


class ChapterBrief(BaseModel):
    title: str
    summary: str


class User(BaseDocument):
    email: str
    password_hash: str
    name: str
    tier: str = "free"
    premium_active: bool = False
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Book(BaseDocument):
    user_id: str
    title: str = "Generating..."
    book_type: str
    genre: str = ""
    tone: str = ""
    length: str
    prompt: str
    premise: str = ""
    characters: List[Character] = []
    plot_threads: List[str] = []
    running_summary: str = ""
    outline: List[ChapterBrief] = []
    total_chapters: int = 0
    current_chapter: int = 0
    status: str = "pending"
    error: Optional[str] = None
    cover_image_url: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Chapter(BaseDocument):
    book_id: str
    index: int
    title: str
    content: str = ""
    word_count: int = 0
    status: str = "pending"
    image_url: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
