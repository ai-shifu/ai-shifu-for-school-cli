---
name: school-review
description: 查询 AI-Shifu for school 的课堂提交、反馈、线上学习记录及班级操作记录，整理有据可查的教学回顾和建议。
---

## 数据查询

先读取 `ai-shifu-for-school skills read school-shared`，明确班级、课程、课次及老师希望了解的问题。

```bash
ai-shifu-for-school activity list <lesson_id>
ai-shifu-for-school activity get <activity_id>
ai-shifu-for-school submission list <activity_id>
ai-shifu-for-school online records <course_bid>
ai-shifu-for-school audit list <class_id>
```

活动的 `recipient_count` 是实际接收名单人数，`submitted_count` 是提交过的学生数；提交数组保留历史版本，不能直接把数组长度当作完成学生人数。按学生区分最新作业与历史修订，复答也不与初答混算。

线上学习记录当前最多返回最新 300 条，班级审计最多返回最新 200 条。明确数据范围及是否截断，不能把这类响应当成完整学期数据；若需更完整范围，先确认平台是否已提供接口。

## 解释与反馈

区分实际提交／完成状态、老师已有评分与本次建议。未提交不等于不理解，完成也不等于掌握；没有测评证据不生成掌握度或效果结论。避免在不需要时列出学生个人信息。

查看或汇总记录不代表授权修改内容或评分。用户要求反馈时，先以对应原始提交为依据形成具体反馈，再通过 `submission feedback` 保存并读回核对。
