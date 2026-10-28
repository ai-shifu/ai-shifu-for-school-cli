---
name: school-shared
description: 连接 AI-Shifu for school，检查老师身份、发现 CLI 能力、判断操作结果和恢复失败。供学校班级、课堂、线上课与教学记录操作共同使用。
---

## 平台入口与身份

使用 `ai-shifu-for-school`。先读取 `--help` 或 `schema <命令>`，不猜测参数和资源 ID。CLI 参数中的 `course_id` 是课堂课程的整数 ID，`course_bid` 是线上课程 BID，两者不可互换。

命令尚未安装时先阅读 [客户端安装](references/install.md)。首次使用可运行 `ai-shifu-for-school setup`，统一完成域名配置、选择 Skills 安装目标和登录；不需要访问学校平台源码仓库。

老师先在终端执行 `ai-shifu-for-school config init` 填写学校域名，再执行 `ai-shifu-for-school auth login <账号>` 交互输入密码。首次联网且尚未配置时也会询问域名，保存至 `~/.config/ai-shifu-for-school/.env` 的 `SCHOOL_SERVER_URL`，以后自动读取。域名应是服务根地址，不带 `/classroom` 网页路径。智能体不向对话索取密码、不读取会话文件。

用 `config show` 查看生效地址；用户已明确指定目标域名时可用 `config set-server <域名>` 保存。地址优先级为本次 `--server`、进程环境变量 `SCHOOL_SERVER_URL`、本机 .env。`--server` 只临时覆盖，不改配置，也不复制其他平台的登录会话。后续保持同一平台与 `--session-file`，失败时不得擅自切换。Docker 本地入口可显式配置为 `http://127.0.0.1:3030`；独立课堂服务为 `http://127.0.0.1:8766`，没有隐式本机默认值。非交互环境缺少配置时返回错误，请老师在终端设置；读取 Skills 和 schema 不需要配置。

用 `auth me` 验证身份，用 `doctor` 检查平台及线上引擎连接。登录失效时请老师重新在终端登录，不改用其他账号或官方站点。教学内容编写和本地 Skills 阅读不需要登录。

## 操作与结果

业务结果为 `{"ok":true,"data":...}`；失败为 `{"ok":false,"error":{"kind":"...","message":"..."}}`，退出码非零。`skills read` 输出 Markdown，流式调试输出 SSE，不按普通 JSON 判断。

`error.kind` 区分 `configuration`、`input`、`authentication`、`permission`、`not_found`、`conflict`、`network` 和 `service`。看不到目标时先核对身份和权限，不将没有结果解释为可以新建替代对象。版本冲突保留本地修改；在新目录拉取、比较并合并后再保存。

内容较长时使用 UTF-8 文件或 `--data @请求.json`，`--data @-` 从标准输入读取。数组和对象字段选项传 JSON，例如 `--class-ids '[1,2]'`。`--query` 接受 JSON 对象。需要未封装能力时先核对接口，再使用 `api METHOD /api/...`，仍受平台权限校验。

## 写入与恢复

明确目标、影响和用户已授权范围。发布、向班级开放、发放活动、公布答案、反馈评分、删除章节或替换班级名单会影响真实使用者；需要澄清时先准备可检查的结果，再询问缺失决定。已有明确授权无需重复确认。只要求草稿时保持草稿。

可用 `--dry-run` 预览。预览不执行修改，也不保证远端权限及当前课堂状态允许执行。不能因为预览成功就声称操作已完成。

写操作不自动重试。网络失败可能意味着远端已完成，先查询状态和返回 ID；多步创建查看完成步骤及本地创建记录。仅向用户报告实际完成及读回验证的结果，不将接口成功等同于教学效果已验证。
