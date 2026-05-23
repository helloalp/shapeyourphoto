param(
    [string]$ExePath = ".\ShapeYourPhoto.exe",
    [int]$Seconds = 8
)

$resolved = Resolve-Path -LiteralPath $ExePath -ErrorAction Stop
$root = Split-Path -Parent $resolved.Path
$before = Get-Process | Where-Object { $_.ProcessName -match '^(ShapeYourPhoto|pythonw|python)$' } | Select-Object -ExpandProperty Id
$process = Start-Process -FilePath $resolved.Path -WorkingDirectory $root -PassThru -WindowStyle Hidden
Start-Sleep -Seconds $Seconds
try {
    $children = Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object { $_.ParentProcessId -eq $process.Id }
} catch {
    $children = @()
    Write-Output "Process child inspection skipped: $($_.Exception.Message)"
}
$after = Get-Process | Where-Object {
    $_.ProcessName -match '^(ShapeYourPhoto|pythonw|python)$' -and ($before -notcontains $_.Id)
}

if ($process.HasExited -and $after.Count -eq 0) {
    throw "ShapeYourPhoto.exe exited before a GUI/runtime process was observed."
}

$consoleChildren = $children | Where-Object { $_.Name -match '^(cmd|powershell|conhost)(\.exe)?$' }
if ($consoleChildren.Count -gt 0) {
    throw "Unexpected console helper remained after launch: $($consoleChildren.Name -join ', ')"
}

foreach ($item in $after) {
    try {
        Stop-Process -Id $item.Id -Force -ErrorAction SilentlyContinue
    } catch {
    }
}
try {
    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
} catch {
}

Write-Output "Windows launcher smoke passed."
