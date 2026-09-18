# lorascape\license\normalize.py 를 licenser_tool 쪽에 심볼릭 링크로 연결
# (관리자 권한 없으면 심볼릭 링크가 조용히 실패하는 PowerShell 특성 때문에
#  -ErrorAction Stop을 반드시 붙여야 try/catch가 제대로 작동함)
$source = Resolve-Path "lorascape\license\normalize.py"
$target = "licenser_tool\normalize.py"

if (Test-Path $target) { Remove-Item $target -Force }

try {
    New-Item -ItemType SymbolicLink -Path $target -Target $source -ErrorAction Stop | Out-Null
    Write-Host "심볼릭 링크 생성 완료 (source of truth: lorascape\license\normalize.py)"
} catch {
    Write-Host "심볼릭 링크 실패(관리자 권한 필요). 대신 파일을 복사합니다."
    Copy-Item $source $target -Force
    Write-Host "복사 완료 — 주의: 앞으로 normalize.py 수정할 때마다 이 스크립트를 다시 실행해야 함"
}
