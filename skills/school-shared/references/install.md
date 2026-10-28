## 安装学校客户端

公开客户端项目为 [ai-shifu/ai-shifu-for-school-cli](https://github.com/ai-shifu/ai-shifu-for-school-cli)，包含 CLI 与 Skills，不包含学校平台服务端。先读取当前 README 的安装说明，确认仓库已发布相应文件，不猜测 npm 或 PyPI 包名。

已有 uv 时可从该公开仓库的源码压缩包安装：

```bash
uv tool install --python 3.12 https://github.com/ai-shifu/ai-shifu-for-school-cli/archive/refs/heads/main.zip
ai-shifu-for-school setup
```

没有 uv 时，仓库提供 macOS / Linux 的 `install.sh` 和 Windows PowerShell 的 `install.ps1`。遵循宿主对软件安装及网络访问的授权要求；不要通过下载学校平台私有仓库来解决 CLI 缺失。

`setup` 需要用户在终端交互填写域名、选择宿主并输入已有平台账号。非交互环境不代填密码或无意义等待，可先安装 CLI，再请用户在终端完成设置。用户已配置时用 `config show` 和 `auth me` 核对，不必重新安装或登录。

标准 Skill 安装器也可通过 `npx skills add ai-shifu/ai-shifu-for-school-cli` 安装这些 Skill 文件；这一步不等于已经安装 CLI。
