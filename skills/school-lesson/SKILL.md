---
name: school-lesson
description: 在 AI-Shifu for school 中备课、组织课次、创建和发放签到、点名、随堂练习与课后作业，查看提交并反馈评分。
---

## 备课

先读取 `ai-shifu-for-school skills read school-shared`。根据老师目标选择班级、课堂课程和课次，复用已有对象。教学内容要适合指定年级及来源，不为使用功能强行增加活动。

```bash
ai-shifu-for-school course list
ai-shifu-for-school course create --title "分数入门" --class-ids '[1]'
ai-shifu-for-school lesson list <course_id>
ai-shifu-for-school lesson create <course_id> --title "认识二分之一" --objectives "理解整体平均分成两份"
ai-shifu-for-school schema activity create
ai-shifu-for-school activity create <lesson_id> --data @活动.json --dry-run
```

活动 `kind` 为 `attendance`、`rollcall`、`exercise` 或 `homework`。请求必须指定 `class_id`、`kind`、`title`。选择题的选项和参考答案放入 `config`，截止时间必须带时区；点名指定真实学生 `target_user_id`。草稿活动创建后不会发给学生。

## 授课与反馈

```bash
ai-shifu-for-school lesson state <lesson_id> <class_id>
ai-shifu-for-school lesson start <lesson_id> <class_id>
ai-shifu-for-school activity list <lesson_id>
ai-shifu-for-school activity start <activity_id>
ai-shifu-for-school submission list <activity_id>
ai-shifu-for-school activity end <activity_id>
ai-shifu-for-school submission feedback <submission_id> --comment "请说明平均分的依据" --score 80
```

随堂练习结束后才能 `activity retry` 或 `activity reveal`；公布参考答案与发起复答是不同操作。点名回应使用 `activity rollcall <activity_id> --responded true`，由老师确认。下课前结束当前课堂活动，作业可独立发布。

平台保存发放时接收名单，新加入学生不会自动收到旧活动。学生只能看自己的提交和反馈，不通过老师能力代替学生作答。不假称已支持分组、文件作业或 AI 自动评分。
