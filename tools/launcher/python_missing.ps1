[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
Write-Host ""
Write-Host "未找到 Python / Python was not found."
Write-Host ""
$arch = if ([Environment]::Is64BitOperatingSystem) { "64-bit" } else { "32-bit" }
$os = (Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue)
$osName = if ($os) { "$($os.Caption) $($os.Version)" } else { "Windows" }
Write-Host "检测到系统 / Detected system: $osName, $arch"
Write-Host ""
Write-Host "源码包需要先安装 Python 3.10 或更新版本。"
Write-Host "The source package needs Python 3.10 or newer."
Write-Host ""
$winget = Get-Command winget -ErrorAction SilentlyContinue
if ($winget) {
    Write-Host "已检测到 winget。可以自动打开 Python 官方安装流程。"
    Write-Host "winget is available and can install the official Python package."
    $answer = Read-Host "输入 Y 开始安装 Python 3.12，或直接按 Enter 手动安装 / Type Y to install Python 3.12, or press Enter for manual steps"
    if ($answer -match '^[Yy]$') {
        Write-Host ""
        Write-Host "正在启动 Python 安装。安装窗口关闭后，请重新双击 start.bat。"
        Write-Host "Starting Python install. After it finishes, run start.bat again."
        try {
            winget install --id Python.Python.3.12 --source winget --scope user --accept-package-agreements --accept-source-agreements
            if ($LASTEXITCODE -eq 0) {
                Write-Host ""
                Write-Host "Python 安装命令已完成。请关闭此窗口后重新运行 start.bat。"
            } else {
                Write-Host ""
                Write-Host "Python 安装未完成，退出代码：$LASTEXITCODE"
                Write-Host "请使用下面的官网地址手动安装。"
            }
        } catch {
            Write-Host ""
            Write-Host "自动安装未完成：$($_.Exception.Message)"
            Write-Host "请使用下面的官网地址手动安装。"
        }
    }
} else {
    Write-Host "未检测到 winget。请使用官网下载安装程序。"
    Write-Host "winget was not found. Please use the official installer."
}
Write-Host ""
Write-Host "官网 / Official download: https://www.python.org/downloads/windows/"
Write-Host "安装时请勾选 Add python.exe to PATH，或安装后重新打开终端再运行 start.bat。"
Write-Host ""
Read-Host "按 Enter 关闭 / Press Enter to close"
