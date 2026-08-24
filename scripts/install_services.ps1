<#
.SYNOPSIS
    把 CafeMatch 的後端與前端註冊成 Windows 服務（透過 NSSM）。

.DESCRIPTION
    註冊之後：開機自動啟動、登出不會停、當掉會自動拉回來，
    不再依賴桌面上那兩個 cmd 視窗。

    這支腳本「不會」自己下載 NSSM。請先自行從 https://nssm.cc/download
    取得 nssm.exe（約 350 KB），解壓後把 win64\nssm.exe 放到 PATH 中，
    或用 -NssmPath 指定完整路徑。

.NOTES
    必須以「系統管理員」身分執行 PowerShell，否則建立服務會失敗。

.EXAMPLE
    # 安裝（以系統管理員開啟 PowerShell）
    .\scripts\install_services.ps1 -NssmPath C:\tools\nssm.exe

.EXAMPLE
    # 移除
    .\scripts\install_services.ps1 -Uninstall -NssmPath C:\tools\nssm.exe
#>

[CmdletBinding()]
param(
    [string]$NssmPath = 'nssm',
    [string]$ProjectRoot,
    [switch]$Uninstall
)

$ErrorActionPreference = 'Stop'

# 專案根目錄：不能寫在 param() 的預設值裡，
# PowerShell 5.1 在參數繫結階段還沒填好 $PSScriptRoot，會拿到空字串。
if (-not $ProjectRoot) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $ProjectRoot = Split-Path -Parent $scriptDir
}

$BackendName  = 'CafeMatchBackend'
$FrontendName = 'CafeMatchFrontend'

# ── 前置檢查 ──────────────────────────────────────────────
$principal = New-Object Security.Principal.WindowsPrincipal(
    [Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error '需要系統管理員權限。請以「以系統管理員身分執行」開啟 PowerShell 後重跑。'
}

$nssm = (Get-Command $NssmPath -ErrorAction SilentlyContinue)
if (-not $nssm) {
    Write-Error @"
找不到 nssm。請先從 https://nssm.cc/download 下載（約 350 KB），
解壓後把 win64\nssm.exe 放進 PATH，或用 -NssmPath 指定完整路徑。
"@
}
$nssm = $nssm.Source

# ── 移除模式 ──────────────────────────────────────────────
if ($Uninstall) {
    foreach ($svc in @($BackendName, $FrontendName)) {
        if (Get-Service -Name $svc -ErrorAction SilentlyContinue) {
            Write-Host "停止並移除 $svc ..."
            & $nssm stop $svc confirm | Out-Null
            & $nssm remove $svc confirm | Out-Null
        } else {
            Write-Host "$svc 不存在，略過"
        }
    }
    Write-Host '移除完成。' -ForegroundColor Green
    return
}

# ── 路徑檢查 ──────────────────────────────────────────────
$python  = Join-Path $ProjectRoot 'venv\Scripts\python.exe'
$runner  = Join-Path $ProjectRoot 'scripts\run_backend_service.py'
$logDir  = Join-Path $ProjectRoot 'logs'
$frontend = Join-Path $ProjectRoot 'frontend'

foreach ($p in @($python, $runner, $frontend)) {
    if (-not (Test-Path $p)) { Write-Error "找不到：$p" }
}
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$npm = (Get-Command npm.cmd -ErrorAction SilentlyContinue)
if (-not $npm) { Write-Error '找不到 npm.cmd，請確認 Node.js 已安裝且在 PATH 中。' }
$npm = $npm.Source

# ── 後端 ──────────────────────────────────────────────────
# 重跑這支腳本時，install 那行會報「already exists」，那是預期的；
# 後面的 set 仍然會套用，等於更新設定。
Write-Host "註冊 $BackendName ..." -ForegroundColor Cyan
& $nssm install $BackendName $python $runner
& $nssm set $BackendName AppDirectory $ProjectRoot
& $nssm set $BackendName DisplayName 'CafeMatch 後端 API'
& $nssm set $BackendName Description '啡你莫屬 Flask 後端（waitress，埠 5000）'
& $nssm set $BackendName Start SERVICE_AUTO_START
# 服務自身的 stdout/stderr（run_backend_service.py 另外會寫 logs\backend.log）
& $nssm set $BackendName AppStdout (Join-Path $logDir 'backend.service.log')
& $nssm set $BackendName AppStderr (Join-Path $logDir 'backend.service.log')
& $nssm set $BackendName AppRotateFiles 1
& $nssm set $BackendName AppRotateBytes 5242880
# 掛掉時自動重啟：等 5 秒再拉起來，避免壞掉時瘋狂重試
& $nssm set $BackendName AppExit Default Restart
& $nssm set $BackendName AppRestartDelay 5000
# MySQL 沒起來的話後端會連不上資料庫，所以要排在它後面。
# 服務名不寫死：XAMPP 用核取方塊裝出來的叫 mysql（小寫），
# MySQL 官方安裝程式則可能是 MySQL80 之類，自動找比較保險。
$mysqlSvc = Get-Service | Where-Object { $_.Name -match '^mysql' } | Select-Object -First 1
if ($mysqlSvc) {
    Write-Host "  找到資料庫服務 $($mysqlSvc.Name)，設為啟動相依" -ForegroundColor DarkGray
    & $nssm set $BackendName DependOnService $mysqlSvc.Name
} else {
    Write-Warning @"
找不到 MySQL 服務，略過啟動相依設定。
資料庫若不是以 Windows 服務執行，重開機後後端會起來但連不上資料庫
（服務不會崩潰，只是查資料的請求會失敗，等資料庫上線就恢復）。
XAMPP 使用者：以系統管理員開啟控制面板，勾選 MySQL 左邊的 Service 核取方塊。
"@
}

# ── 前端 ──────────────────────────────────────────────────
# 用 preview 而不是 dev：preview 服務的是編譯後的靜態檔，
# 沒有 HMR、不會即時編譯，長時間掛著跑穩定得多。
# 注意：改完前端程式碼要重新 npm run build，服務不會自己重編。
Write-Host "註冊 $FrontendName ..." -ForegroundColor Cyan
& $nssm install $FrontendName $npm 'run preview'
& $nssm set $FrontendName AppDirectory $frontend
& $nssm set $FrontendName DisplayName 'CafeMatch 前端網站'
& $nssm set $FrontendName Description '啡你莫屬 Vite preview（埠 5173，服務 dist 靜態檔）'
& $nssm set $FrontendName Start SERVICE_AUTO_START
& $nssm set $FrontendName AppStdout (Join-Path $logDir 'frontend.service.log')
& $nssm set $FrontendName AppStderr (Join-Path $logDir 'frontend.service.log')
& $nssm set $FrontendName AppRotateFiles 1
& $nssm set $FrontendName AppRotateBytes 5242880
& $nssm set $FrontendName AppExit Default Restart
& $nssm set $FrontendName AppRestartDelay 5000

Write-Host ''
Write-Host '註冊完成。啟動之前還有一件事：' -ForegroundColor Yellow
Write-Host '  前端服務跑的是 preview，需要先有編譯結果：'
Write-Host '    cd frontend; npm run build'
Write-Host ''
Write-Host '接著啟動：'
Write-Host "    nssm start $BackendName"
Write-Host "    nssm start $FrontendName"
Write-Host ''
Write-Host '確認狀態：'
Write-Host "    Get-Service $BackendName, $FrontendName"
Write-Host '日誌：logs\backend.log（應用程式）、logs\*.service.log（服務層）'
