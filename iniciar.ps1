param([switch]$Automatizar, [ValidateRange(1024,65535)][int]$Puerto = 8765)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Ejecuta instalar.ps1 primero.' }
$worker = $null
if ($Automatizar) {
    New-Item -ItemType Directory -Path 'data' -Force | Out-Null
    $worker = Start-Process -FilePath $pythonPath -ArgumentList @('-m', 'pulso.cli', 'watch', '--limit', '2', '--interval', '86400') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $PSScriptRoot 'data\worker.log') -RedirectStandardError (Join-Path $PSScriptRoot 'data\worker-error.log') -PassThru
}
try {
    Write-Host "PulsoTerritorial: http://127.0.0.1:$Puerto"
    & $pythonPath -m pulso.web --port $Puerto
} finally {
    if ($null -ne $worker -and -not $worker.HasExited) { Stop-Process -InputObject $worker }
}
