# Estación local de PulsoTerritorial.
# Los servidores del MINAM (SINIA y GEOPERÚ) responden 403 a GitHub Actions. Este script corre
# esas dos fuentes desde una laptop en Perú, versiona el resultado en demo_data/ y lo sube;
# el workflow diario publica siempre la copia más reciente. No guarda ni usa claves.
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
& $python -m pulso.pipeline --estacion
if ($LASTEXITCODE -ne 0) { throw 'La estación local no terminó.' }
git add demo_data/sources/ogasa.json demo_data/geoperu_*.json demo_data/station_log.json
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    git commit -m "Estación local: SINIA y GEOPERÚ $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
    git pull --rebase --quiet
    git push --quiet
}
