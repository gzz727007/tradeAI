# ==============================================================
# A股可转债商业级 AI 量化投研与多账号实盘终端
# ==============================================================

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONUTF8 = "1"
Set-Location -Path $PSScriptRoot

Clear-Host
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "   📈 A股可转债商业级 AI 量化投研与多账号实盘终端 (tradeAI)" -ForegroundColor Yellow
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "🚀 正在启动金融量化 SaaS 终端服务 (FastAPI + React 19)..." -ForegroundColor Green
Write-Host ""
Write-Host "💡 访问地址:" -ForegroundColor Cyan
Write-Host "   • 生产一体化终端: http://localhost:8088" -ForegroundColor Yellow
Write-Host "   • 交互式 API 文档: http://localhost:8088/docs" -ForegroundColor Gray
Write-Host ""
Write-Host "👉 正在检测端口并自动唤起浏览器 (就绪后秒开)..." -ForegroundColor Cyan

Start-Job -ScriptBlock {
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Milliseconds 600
        $conn = Get-NetTCPConnection -LocalPort 8088 -State Listen -ErrorAction SilentlyContinue
        if ($conn) {
            Start-Process "http://localhost:8088"
            break
        }
    }
} | Out-Null

Write-Host ""
Write-Host "✅ 服务已就绪！如需退出终端请按 Ctrl + C" -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""

& ".\.venv\Scripts\python.exe" -m uvicorn server.main:app --host 0.0.0.0 --port 8088 --reload
