---
name: school-class
description: 在 AI-Shifu for school 中创建和查询班级、查看成员、开通学生账号并加入班级。适用于老师管理班级与学生。
---

## 使用

先通过 `ai-shifu-for-school skills read school-shared` 读取公共操作规则。查询真实班级及成员，解决重名目标后再修改：

```bash
ai-shifu-for-school class list
ai-shifu-for-school class create --name "三年级一班" --dry-run
ai-shifu-for-school class members <class_id>
ai-shifu-for-school class add-member <class_id> <student_id>
ai-shifu-for-school student create --username <账号> --display-name <姓名> --class-id <class_id>
```

开通学生时，老师自行在终端输入初始密码；不要把密码放在命令参数、对话或操作结果里。已存在的学生使用添加成员命令，不重复开通账号。不要伪造批量导入、移除成员、教师共同任教或密码找回能力；需要这些能力时先核对 `schema` 和已开放接口。

操作后读回班级与成员确认结果。班级码属于班级加入凭据，只向用户请求的对象展示，不附带传播。
