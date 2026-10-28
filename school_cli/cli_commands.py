"""One command catalogue drives argument parsing, help and schema discovery."""

from dataclasses import dataclass
from typing import Literal

from pydantic import Field

from . import schemas as S

ONLINE = "/api/online/shifu/shifus/{course_bid}"


class OnlineCreate(S.Input):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""


class OutlineCreate(OnlineCreate):
    parent_bid: str = ""


class Assignment(S.Input):
    class_ids: list[int] = Field(max_length=50)


class OnlineUpdate(S.Input):
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    avatar: str | None = None
    keywords: list[str] | None = None
    model: str | None = None
    use_learner_language: bool | None = None
    ask_enabled_status: Literal[5101, 5102, 5103] | None = None
    ask_model: str | None = None
    ask_system_prompt: str | None = None
    ask_provider_config: dict | None = None
    tts_enabled: bool | None = None
    tts_provider: str | None = None
    tts_model: str | None = None
    tts_voice_id: str | None = None
    tts_speed: float | None = None
    tts_pitch: int | None = None
    tts_emotion: str | None = None
    default_listen_mode_enabled: bool | None = None


class OutlineUpdate(S.Input):
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    is_hidden: bool | None = None
    type: Literal["normal", "trial", "guest"] | None = None


class OutlineOrder(S.Input):
    order: list[str] = Field(min_length=1)


class VariableCreate(S.Input):
    profile_key: str = Field(min_length=1)
    parent_id: str | None = None


class VariableUpdate(VariableCreate):
    profile_id: str = Field(min_length=1)
    profile_type: Literal["text"]


class VariableDelete(S.Input):
    profile_id: str = Field(min_length=1)
    parent_id: str | None = None


class DebugRequest(S.Input):
    input: dict[str, list[str]] | None = None
    input_type: str | None = None
    language: str | None = None
    listen: bool | None = None
    learning_mode: str | None = None
    reload_generated_block_bid: str | None = None
    reload_element_bid: str | None = None


@dataclass(frozen=True)
class Command:
    name: str
    method: str
    path: str
    arguments: tuple[str, ...] = ()
    model: type | None = None
    description: str = ""
    handler: str = "request"

    def schema(self):
        return {
            "command": "ai-shifu-for-school " + self.name,
            "method": self.method,
            "path": self.path,
            "arguments": list(self.arguments),
            "input": self.model.model_json_schema() if self.model else None,
            "description": self.description,
            "dry_run": self.method != "GET"
            or self.handler in {"pull", "save", "create_directory"},
        }


COMMANDS = [
    Command(
        "auth login",
        "POST",
        "/api/auth/login",
        ("username",),
        description="在终端交互输入密码登录",
        handler="login",
    ),
    Command("auth me", "GET", "/api/auth/me", description="查询当前账号"),
    Command(
        "auth logout",
        "POST",
        "/api/auth/logout",
        description="注销当前会话",
        handler="logout",
    ),
    Command("class list", "GET", "/api/classes"),
    Command("class create", "POST", "/api/classes", model=S.ClassCreate),
    Command("class members", "GET", "/api/classes/{class_id}/members", ("class_id",)),
    Command(
        "class add-member",
        "POST",
        "/api/classes/{class_id}/members/{student_id}",
        ("class_id", "student_id"),
    ),
    Command(
        "student create",
        "POST",
        "/api/students",
        model=S.StudentCreate,
        handler="student",
    ),
    Command("course list", "GET", "/api/courses"),
    Command("course create", "POST", "/api/courses", model=S.CourseCreate),
    Command(
        "course bind",
        "POST",
        "/api/courses/{course_id}/classes/{class_id}",
        ("course_id", "class_id"),
    ),
    Command("lesson list", "GET", "/api/courses/{course_id}/lessons", ("course_id",)),
    Command(
        "lesson create",
        "POST",
        "/api/courses/{course_id}/lessons",
        ("course_id",),
        S.LessonCreate,
    ),
    Command(
        "lesson update",
        "PUT",
        "/api/lessons/{lesson_id}",
        ("lesson_id",),
        S.LessonCreate,
    ),
    Command(
        "lesson state",
        "GET",
        "/api/lessons/{lesson_id}/classes/{class_id}/state",
        ("lesson_id", "class_id"),
    ),
    Command(
        "lesson start",
        "POST",
        "/api/lessons/{lesson_id}/classes/{class_id}/start",
        ("lesson_id", "class_id"),
    ),
    Command(
        "lesson end",
        "POST",
        "/api/lessons/{lesson_id}/classes/{class_id}/end",
        ("lesson_id", "class_id"),
    ),
    Command(
        "activity list", "GET", "/api/lessons/{lesson_id}/activities", ("lesson_id",)
    ),
    Command(
        "activity create",
        "POST",
        "/api/lessons/{lesson_id}/activities",
        ("lesson_id",),
        S.ActivityCreate,
    ),
    Command(
        "activity update",
        "PUT",
        "/api/activities/{activity_id}",
        ("activity_id",),
        S.ActivityCreate,
    ),
    Command("activity get", "GET", "/api/activities/{activity_id}", ("activity_id",)),
    *[
        Command(
            f"activity {action}",
            "POST",
            "/api/activities/{activity_id}/" + action,
            ("activity_id",),
        )
        for action in ("start", "end", "retry", "reveal")
    ],
    Command(
        "activity rollcall",
        "POST",
        "/api/activities/{activity_id}/rollcall",
        ("activity_id",),
        S.RollcallResult,
    ),
    Command(
        "submission list",
        "GET",
        "/api/activities/{activity_id}",
        ("activity_id",),
        handler="submissions",
    ),
    Command(
        "submission feedback",
        "POST",
        "/api/submissions/{submission_id}/feedback",
        ("submission_id",),
        S.Feedback,
    ),
    Command("audit list", "GET", "/api/classes/{class_id}/audit", ("class_id",)),
    Command(
        "online list",
        "GET",
        "/api/platform/online-courses",
        description="平台课程目录；引擎分页查询可用 api",
    ),
    Command("online show", "GET", ONLINE + "/detail", ("course_bid",)),
    Command("online create", "PUT", "/api/online/shifu/shifus", model=OnlineCreate),
    Command(
        "online update",
        "POST",
        ONLINE + "/detail",
        ("course_bid",),
        OnlineUpdate,
        handler="metadata",
        description="只更新提供的字段；必须提供 --base-revision 或 --course-dir",
    ),
    Command(
        "online publish",
        "POST",
        ONLINE + "/publish",
        ("course_bid",),
        description="发布草稿；不会自动向班级开放",
    ),
    Command(
        "online assign",
        "PUT",
        "/api/platform/online-courses/{course_bid}/classes",
        ("course_bid",),
        Assignment,
        "完整替换开放班级；空数组表示撤回全部班级授权",
    ),
    Command(
        "online records",
        "GET",
        "/api/online/school/records/{course_bid}",
        ("course_bid",),
        description="学习记录；当前平台最多返回最新 300 条",
    ),
    Command("online outline list", "GET", ONLINE + "/outlines", ("course_bid",)),
    Command(
        "online outline create",
        "PUT",
        ONLINE + "/outlines",
        ("course_bid",),
        OutlineCreate,
    ),
    Command(
        "online outline update",
        "POST",
        ONLINE + "/outlines/{outline_bid}",
        ("course_bid", "outline_bid"),
        OutlineUpdate,
        description="更新章节或课时属性；--data 为要修改的字段",
    ),
    Command(
        "online outline delete",
        "DELETE",
        ONLINE + "/outlines/{outline_bid}",
        ("course_bid", "outline_bid"),
    ),
    Command(
        "online outline reorder",
        "PATCH",
        ONLINE + "/outlines/reorder",
        ("course_bid",),
        OutlineOrder,
        description='--data 为 {"order":[同一父节点下的全部 BID]}',
    ),
    Command(
        "online lesson show",
        "GET",
        ONLINE + "/outlines/{outline_bid}/mdflow",
        ("course_bid", "outline_bid"),
    ),
    Command(
        "online lesson history",
        "GET",
        ONLINE + "/outlines/{outline_bid}/mdflow/history",
        ("course_bid", "outline_bid"),
    ),
    Command(
        "online lesson update",
        "POST",
        ONLINE + "/outlines/{outline_bid}/mdflow",
        ("course_bid", "outline_bid"),
        handler="content",
        description="--file UTF-8 提示词；必须提供 --base-revision 或 --course-dir",
    ),
    Command(
        "online debug",
        "PUT",
        "/api/online/learn/shifu/{course_bid}/run/{outline_bid}",
        ("course_bid", "outline_bid"),
        DebugRequest,
        handler="debug",
        description="流式调试草稿；会调用已配置模型",
    ),
    Command(
        "online variable list",
        "GET",
        "/api/online/profiles/get-profile-item-definitions",
        ("course_bid",),
        handler="variables",
    ),
    *[
        Command(
            f"online variable {name}",
            "POST",
            "/api/online/profiles/" + route,
            ("course_bid",),
            model,
            handler="variables",
        )
        for name, route, model in (
            ("create", "add-profile-item-quick", VariableCreate),
            ("update", "save-profile-item", VariableUpdate),
            ("delete", "delete-profile-item", VariableDelete),
        )
    ],
    Command(
        "online resource upload",
        "POST",
        "/api/online/shifu/upfile",
        handler="upload",
        description="--file 本地资源；返回平台资源 URL",
    ),
    Command(
        "online pull",
        "GET",
        ONLINE,
        ("course_bid",),
        handler="pull",
        description="读取草稿到 --course-dir；保留不同的本地文件备份",
    ),
    Command(
        "online status",
        "GET",
        ONLINE,
        handler="status",
        description="比较 --course-dir 的本地内容和远端版本",
    ),
    Command(
        "online save",
        "POST",
        ONLINE,
        handler="save",
        description="保存 --course-dir 中已绑定的课程提示词及课时修改；不重建章节",
    ),
    Command(
        "online create-from-dir",
        "PUT",
        "/api/online/shifu/shifus",
        handler="create_directory",
        description="从 --course-dir 逐步创建整课草稿；保存步骤供恢复，不发布",
    ),
]

BY_NAME = {command.name: command for command in COMMANDS}
