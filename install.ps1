param([switch]$SkipSetup)
$ErrorActionPreference = 'Stop'

$UvCommand = Get-Command uv -ErrorAction SilentlyContinue
if ($UvCommand) {
    $UvBin = $UvCommand.Source
} else {
    $UvBin = Join-Path $HOME '.local/bin/uv.exe'
    if (-not (Test-Path $UvBin)) {
        Write-Host '正在安装 uv，用于管理客户端运行环境……'
        Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    }
    if (-not (Test-Path $UvBin)) {
        throw '未找到 uv，请按 uv 安装提示重新打开终端后重试。'
    }
}

$SourceUrl = 'https://github.com/ai-shifu/ai-shifu-for-school-cli/archive/refs/heads/main.zip'
& $UvBin tool install --python 3.12 --reinstall $SourceUrl
if ($LASTEXITCODE -ne 0) { throw '客户端安装失败；如装过旧测试包，请先按 README 卸载旧工具。' }
$ToolBin = (& $UvBin tool dir --bin).Trim()
if ($LASTEXITCODE -ne 0) { throw '未能确定 CLI 安装目录。' }
& $UvBin tool update-shell
if ($LASTEXITCODE -ne 0) { throw '未能更新命令路径，请按 uv 提示处理。' }
$ClientBin = Join-Path $ToolBin 'ai-shifu-for-school.exe'
& $ClientBin --version
if ($LASTEXITCODE -ne 0) { throw '客户端安装验证失败。' }
if (-not $SkipSetup -and -not [Console]::IsInputRedirected) {
    & $ClientBin setup
    if ($LASTEXITCODE -ne 0) { throw '设置未完成；可再次运行 ai-shifu-for-school setup。' }
} else {
    Write-Host 'CLI 安装完成。请在终端执行 ai-shifu-for-school setup。'
}
