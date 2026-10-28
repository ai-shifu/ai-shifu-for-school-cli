---
name: school-online-course
description: 为 AI-Shifu for school 编写和审查课程提示词、MarkdownFlow 授课提示词，并通过学校 CLI 创建、编辑、调试、发布及向班级开放线上课程。
---

## 内容编写

先读取公共规则：`ai-shifu-for-school skills read school-shared`。直接从已有主题、材料、课程或待修改提示词开始，复用用户已确定的目标与选择，只询问会改变结果的缺失信息。

按任务读取本 Skill 的参考文件；可用 `ai-shifu-for-school skills read school-online-course references/<文件名>`，也可读取相对本文件的链接：

- 教学设计与内容依据：[teaching-design.md](references/teaching-design.md)。
- 课程级角色与共享规则：[course-prompt.md](references/course-prompt.md)。
- 课时授课指令与示例：[teaching-prompt.md](references/teaching-prompt.md)。
- 交互、记忆及确定性输出：[markdownflow.md](references/markdownflow.md)。
- 质量审查：[review.md](references/review.md)。
- 文件格式、学校命令和冲突恢复：[course-files.md](references/course-files.md)。
- 官方内容的来源及取舍：[sources.md](references/sources.md)。

这些内容由官方课程 Skill 的教学规范适配而来，全部随学校工具包交付。无需安装其他 Skill，也不使用其他 CLI、官方站点授权或官方账号。

## 学校平台操作

```bash
ai-shifu-for-school online list
ai-shifu-for-school online pull <course_bid> --course-dir ./course
ai-shifu-for-school online status --course-dir ./course
ai-shifu-for-school online save --course-dir ./course --dry-run
ai-shifu-for-school online create-from-dir --course-dir ./new-course --dry-run
```

编辑已有课程时先拉取并保留版本基线，再改文件和定点保存；不要整课重建。新课程默认形成可检查的完整草稿。创建、发布和向哪些班级开放，严格遵循老师的授权范围；未授权的状态变化先展示具体结果并询问，不从“写课程”推定发布授权。

```bash
ai-shifu-for-school online debug <course_bid> <outline_bid> --data @调试请求.json
ai-shifu-for-school online publish <course_bid> --dry-run
ai-shifu-for-school online assign <course_bid> --class-ids '[1,2]' --dry-run
```

调试输出 SSE 并实际消耗已配置模型服务。调试请求结构先查接口契约，不把静态提示词检查说成授课已验证。发布不会自动开放班级；`assign` 完整替换名单，空数组会撤回全部班级授权。

资源用 `online resource upload --file <文件>` 上传，仅嵌入实际返回且可访问的地址，不编造 URL。变量用 `online variable` 命令管理，操作前读取对应 `schema` 和现有定义。
