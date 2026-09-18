# build/build_all.ps1 — 본체 + 발급도구를 순서대로 빌드함
Set-Location $PSScriptRoot

Write-Host "=== LoRaScape 본체 빌드 중 ===" -ForegroundColor Cyan
pyinstaller lorascape.spec --noconfirm

Write-Host "`n=== 라이선스 발급 도구 빌드 중 ===" -ForegroundColor Cyan
pyinstaller licenser_tool.spec --noconfirm

Write-Host "`n=== 빌드 완료 ===" -ForegroundColor Green
Write-Host "본체: build\dist\LoRaScape\LoRaScape.exe"
Write-Host "발급도구: build\dist\LoRaScape_Licenser\LoRaScape_Licenser.exe"