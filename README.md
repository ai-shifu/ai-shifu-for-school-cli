## AI-Shifu for school CLI 与 Skills

面向老师的公开客户端：通过学校平台已有账号，管理班级、备课、课堂活动、线上课程及教学记录。

本仓库只包含客户端、请求格式和五个 Skills。学校平台服务端、数据库、运行配置和模型服务凭据不在本仓库中；安装客户端不会自动开通账号。

## 快速开始

需要连接学校平台，并由平台负责人开通老师账号。无需获得学校平台私有仓库权限。

macOS / Linux 可以通过在线安装脚本安装 CLI 并进入配置向导：

```bash
curl -fsSL https://raw.githubusercontent.com/ai-shifu/ai-shifu-for-school-cli/main/install.sh | bash
```

Windows PowerShell：

```powershell
irm https://raw.githubusercontent.com/ai-shifu/ai-shifu-for-school-cli/main/install.ps1 | iex
```

安装脚本使用 uv 安装独立客户端，缺少 Python 时由 uv 准备 Python 3.12。代码从本公开仓库的源码压缩包构建，用户不需要安装 Git、下载整个学校平台或手动定位 wheel 文件。配置向导依次询问学校域名、Skill 安装目标和账号，密码只在终端输入。

脚本在没有交互终端时只安装 CLI；之后在终端运行：

```bash
ai-shifu-for-school setup
```

脚本安装成功后，如当前终端找不到命令，重新打开终端。已经安装过旧的 `ai-shifu-for-school` 测试发行包时，先运行 `uv tool uninstall ai-shifu-for-school`，再安装本客户端；域名配置与登录会话不会被卸载命令删除。

## 已有 uv 时安装

```bash
uv tool install --python 3.12 https://github.com/ai-shifu/ai-shifu-for-school-cli/archive/refs/heads/main.zip
ai-shifu-for-school setup
```

Python 发行包名为 `ai-shifu-for-school-cli`，可执行命令统一为 `ai-shifu-for-school`。本仓库尚不提供 PyPI 或 npm 包名安装入口。

## 分步配置

```bash
ai-shifu-for-school config init
ai-shifu-for-school config show
ai-shifu-for-school auth login teacher_username
ai-shifu-for-school doctor
ai-shifu-for-school class list
ai-shifu-for-school online list
```

学校域名示例为 `https://school.dev.pillowai.cn`，不要附带 `/classroom` 网页路径。地址写入本机 `~/.config/ai-shifu-for-school/.env` 的 `SCHOOL_SERVER_URL`；密码和会话不写入该文件。每次请求的地址优先级为 `--server`、进程环境变量、本机 .env；不会在失败后切换学校或退回本机服务。

`--session-file` 可隔离同一平台的不同账号。Cookie 文件保存在用户配置目录并绑定学校地址，退出使用 `auth logout`。

## 安装 Skills

五个 Skills 分别负责公共连接规则、班级、课堂、线上课程和教学记录。选择一种安装方式即可。

通过客户端安装，以 Codex 为例：

```bash
ai-shifu-for-school skills install --dest ~/.codex/skills
```

也可以由标准 Skill 安装工具从本公开仓库发现并安装：

```bash
npx skills add ai-shifu/ai-shifu-for-school-cli
```

第二种方式需要 Node.js / npx，安装的是 Skills；CLI 仍按前文安装。官方课程 Skill 无需另行安装，教学参考完整随本客户端提供。安装已有不同内容时停止并报告差异，不覆盖用户修改。

重新加载宿主的 Skills 后，可以请求：

> 使用 school-class 查看我在学校平台上的班级和成员。

> 使用 school-online-course 准备一节“认识二分之一”的线上课，保存为草稿，不发布。

## 命令与结果

```bash
ai-shifu-for-school --help
ai-shifu-for-school schema
ai-shifu-for-school schema activity.create
ai-shifu-for-school skills read school-online-course
ai-shifu-for-school class create --name "示例班级" --dry-run
```

业务命令按 `auth`、`class`、`student`、`course`、`lesson`、`activity`、`submission`、`online` 和 `audit` 分组；原始 `api` 命令用于其余已开放接口。输入支持 UTF-8 文件、JSON 文件及标准输入。

普通命令返回 `{"ok":true,"data":...}`，失败返回 `{"ok":false,"error":...}`。`skills read` 输出 Markdown，调试输出 SSE。`--dry-run` 不修改远端数据。所有操作使用真实平台权限，创建、发放、反馈和发布均会真实保存。

## 课程文件与版本

```bash
ai-shifu-for-school online pull COURSE_BID --course-dir ./course
ai-shifu-for-school online status --course-dir ./course
ai-shifu-for-school online save --course-dir ./course --dry-run
```

课程作者输入包括 README、课程介绍、课程提示词、章节结构和 `lessons/` 下的课时文件。完整格式见 [课程文件说明](skills/school-online-course/references/course-files.md)。保存已有课时采用版本基线和定点更新，不全量重建章节。冲突时保留本地内容，另选目录拉取后合并。

元数据采用写前检查，当前平台对同一账号的并发编辑也存在保护限制；避免同时用网页和 CLI 编辑同一课程。发布与向班级开放是独立操作，不从创建草稿推定发布授权。

## 开发与分发检查

```bash
uv sync
uv run pytest -q
uv run ruff check .
uv build
uv run python tools/check_distribution.py dist
```

客户端测试使用模拟 HTTP 响应，不需要学校平台源码、数据库或真实账号。分发检查确认 wheel 和源码包不包含服务端模块、业务数据或运行配置。教学参考来源见 [来源记录](skills/school-online-course/references/sources.md)。

## 许可证

本客户端及随附 Skills 使用 [MIT 许可证](LICENSE)。它不覆盖学校平台服务端、运行数据、第三方服务或原官方课程工具仓库。教学参考的适配说明见 [NOTICE](NOTICE)。
