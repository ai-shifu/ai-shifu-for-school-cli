from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Credentials(Input):
    username: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=10, max_length=128)

    # Password spaces are meaningful and must not be silently altered.
    @field_validator("password", mode="before")
    @classmethod
    def preserve_password(cls, value):
        if not isinstance(value, str):
            raise ValueError("密码必须为字符串")
        if value != value.strip():
            raise ValueError("首版密码不能以空格开头或结尾")
        return value


class Account(Credentials):
    display_name: str = Field(min_length=1, max_length=50)


class StudentCreate(Account):
    class_id: int | None = Field(default=None, ge=1)


class ClassCreate(Input):
    name: str = Field(min_length=1, max_length=80)


class JoinClass(Input):
    join_code: str = Field(min_length=6, max_length=20)


class CourseCreate(Input):
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=5000)
    class_ids: list[int] = Field(default_factory=list, max_length=50)


class LessonCreate(Input):
    title: str = Field(min_length=1, max_length=100)
    objectives: str = Field(default="", max_length=5000)


class ActivityConfig(Input):
    options: list[str] = Field(default_factory=list, max_length=8)
    correct_answer: str = Field(default="", max_length=1000)

    @field_validator("options")
    @classmethod
    def valid_options(cls, value):
        if value and (
            len(value) < 2 or any(not s.strip() or len(s) > 500 for s in value)
        ):
            raise ValueError("选择题需提供2至8个非空选项，每项不超过500字")
        if len(value) != len(set(value)):
            raise ValueError("选项不能重复")
        return value


class ActivityCreate(Input):
    class_id: int = Field(ge=1)
    kind: Literal["attendance", "rollcall", "exercise", "homework"]
    title: str = Field(min_length=1, max_length=120)
    instructions: str = Field(default="", max_length=12000)
    config: ActivityConfig = Field(default_factory=ActivityConfig)
    scheduled_minute: int | None = Field(default=None, ge=0, le=360)
    due_at: datetime | None = None
    allow_late: bool = False
    target_user_id: int | None = Field(default=None, ge=1)

    @field_validator("due_at")
    @classmethod
    def aware_deadline(cls, value):
        if value and value.tzinfo is None:
            raise ValueError("截止时间必须包含时区")
        return value


class Submission(Input):
    answer: str = Field(min_length=1, max_length=12000)
    request_id: str = Field(min_length=8, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")


class Feedback(Input):
    comment: str = Field(min_length=1, max_length=5000)
    score: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)


class RollcallResult(Input):
    responded: bool
