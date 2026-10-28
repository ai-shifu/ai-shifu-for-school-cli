## 本地课程目录

```text
course/
  README.md
  course-description.md
  course-prompt.md
  structure.json
  lessons/
    lesson-01.md
  .school-sync.json
  .school-create.json
```

README 第一行是 `# 课程名`；description 为课程介绍，prompt 为课程级提示词。课时文件保存完整 UTF-8 MarkdownFlow。结构格式：

```json
{"chapters":[{"title":"第一章","lessons":[{"title":"认识二分之一","file":"lesson-01.md"}]}]}
```

课时 file 相对于 `lessons/`，不能越出目录。首版整课创建要求明确章节和课时映射，不读取官方构建产物，也不在文件缺失时静默跳过。`.school-sync.json` 由 CLI 管理平台地址、课程 BID、课时 BID、版本及内容哈希，不能手工伪造；`.school-create.json` 记录分步创建的完成和待确认状态，不含会话凭据。

## 新课与已有课程

```bash
ai-shifu-for-school online create-from-dir --course-dir ./course --dry-run
ai-shifu-for-school online create-from-dir --course-dir ./course
ai-shifu-for-school online pull <course_bid> --course-dir ./editing
ai-shifu-for-school online status --course-dir ./editing
ai-shifu-for-school online save --course-dir ./editing --dry-run
ai-shifu-for-school online save --course-dir ./editing
```

新课逐步创建草稿并读回核对，失败返回完成步骤。记录存在待确认请求时，先核对平台真实状态，不删记录重试创建。已绑定目录不能用来新建替代课程。

拉取先读完远端快照再写本地文件，不同本地内容先生成备份。`save` 更新已绑定的课程名称、介绍、课程提示词和变化的课时正文，不自动删除或重建课时。结构变化使用 `online outline` 命令后重新拉取，避免混淆 BID；先保留本地内容。

单个课时可用 `online lesson update <course_bid> <outline_bid> --file <课时文件> --course-dir <目录>`，也可明确提供编辑前记录的 `--base-revision`。课程设置使用 `online update <course_bid> --data @字段.json --base-revision <版本>`；课程提示词还支持 `--course-prompt-file`。字段名以当前引擎接口为准，遗漏字段不自行补默认值。

## 冲突限制

保存前比较版本，课时正文携带 `base_revision`。冲突时本地内容保留；另选目录拉取后合并，不自动覆盖。课程元数据是写前检查，存在检查与保存之间的并发窗口；当前引擎课时锁对同一账号的并发编辑也不提供完整的强比较保护。不要让同一账号在网页和 CLI 同时改同一课程。

`status` 的 `clean` 只描述其检查范围，线上记录与教学效果不在其中。部分保存失败时返回已完成步骤，不能将整次操作称为已完成，也不能简单重跑整课创建。
