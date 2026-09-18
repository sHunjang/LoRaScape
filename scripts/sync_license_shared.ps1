# lorascape\license\{normalize.py, issuer_core.py} 를 licenser_tool 쪽에 동기화함.
# 이 두 파일은 본체와 발급도구가 반드시 같은 알고리즘을 써야 하는 파일들이라,
# 수정할 때마다 이 스크립트를 돌려서 양쪽을 일치시켜야 함.
$files = @("normalize.py", "issuer_core.py")

foreach ($name in $files) {
    $source = Resolve-Path "lorascape\license\$name"
    $target = "licenser_tool\$name"

    if (Test-Path $target) { Remove-Item $target -Force }

    try {
        New-Item -ItemType SymbolicLink -Path $target -Target $source -ErrorAction Stop | Out-Null
        Write-Host "[$name] 심볼릭 링크 생성 완료"
    } catch {
        Copy-Item $source $target -Force
        Write-Host "[$name] 심볼릭 링크 실패(관리자 권한 필요) - 대신 복사함. 수정 시 재실행 필요"
    }
}