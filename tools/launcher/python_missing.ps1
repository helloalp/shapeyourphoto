[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
Write-Host ""
Write-Host "鏈壘鍒?Python / Python was not found."
Write-Host ""
$arch = if ([Environment]::Is64BitOperatingSystem) { "64-bit" } else { "32-bit" }
$os = (Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue)
$osName = if ($os) { "$($os.Caption) $($os.Version)" } else { "Windows" }
Write-Host "妫€娴嬪埌绯荤粺 / Detected system: $osName, $arch"
Write-Host ""
Write-Host "婧愮爜鍖呴渶瑕佸厛瀹夎 Python 3.10 鎴栨洿鏂扮増鏈€?
Write-Host "The source package needs Python 3.10 or newer."
Write-Host ""
$winget = Get-Command winget -ErrorAction SilentlyContinue
if ($winget) {
    Write-Host "宸叉娴嬪埌 winget銆傚彲浠ヨ嚜鍔ㄦ墦寮€ Python 瀹樻柟瀹夎娴佺▼銆?
    Write-Host "winget is available and can install the official Python package."
    $answer = Read-Host "杈撳叆 Y 寮€濮嬪畨瑁?Python 3.12锛屾垨鐩存帴鎸?Enter 鎵嬪姩瀹夎 / Type Y to install Python 3.12, or press Enter for manual steps"
    if ($answer -match '^[Yy]$') {
        Write-Host ""
        Write-Host "姝ｅ湪鍚姩 Python 瀹夎銆傚畨瑁呯獥鍙ｅ叧闂悗锛岃閲嶆柊杩愯 ShapeYourPhoto.exe锛涙簮鐮佸寘涔熷彲杩愯 start.bat銆?
        Write-Host "Starting Python install. After it finishes, run ShapeYourPhoto.exe again; source trees may also run tools/launcher/start.bat."
        try {
            winget install --id Python.Python.3.12 --source winget --scope user --accept-package-agreements --accept-source-agreements
            if ($LASTEXITCODE -eq 0) {
                Write-Host ""
                Write-Host "Python 瀹夎鍛戒护宸插畬鎴愩€傝鍏抽棴姝ょ獥鍙ｅ悗閲嶆柊杩愯 ShapeYourPhoto.exe銆?
            } else {
                Write-Host ""
                Write-Host "Python 瀹夎鏈畬鎴愶紝閫€鍑轰唬鐮侊細$LASTEXITCODE"
                Write-Host "璇蜂娇鐢ㄤ笅闈㈢殑瀹樼綉鍦板潃鎵嬪姩瀹夎銆?
            }
        } catch {
            Write-Host ""
            Write-Host "鑷姩瀹夎鏈畬鎴愶細$($_.Exception.Message)"
            Write-Host "璇蜂娇鐢ㄤ笅闈㈢殑瀹樼綉鍦板潃鎵嬪姩瀹夎銆?
        }
    }
} else {
    Write-Host "鏈娴嬪埌 winget銆傝浣跨敤瀹樼綉涓嬭浇椤垫墜鍔ㄥ畨瑁呫€?
    Write-Host "winget was not found. Please use the official installer."
}
Write-Host ""
Write-Host "瀹樼綉 / Official download: https://www.python.org/downloads/windows/"
Write-Host "瀹夎鏃惰鍕鹃€?Add python.exe to PATH锛屾垨瀹夎鍚庨噸鏂版墦寮€缁堢鍐嶈繍琛?ShapeYourPhoto.exe銆?
Write-Host ""
Read-Host "鎸?Enter 鍏抽棴 / Press Enter to close"
