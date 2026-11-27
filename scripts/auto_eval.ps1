# Auto eval patrol (schedule with cron / Task Scheduler): ERP eval -> gate -> backflow -> drift
# Windows example (hourly):
#   schtasks /create /tn "HengERP-AutoEval" /tr "powershell -NoProfile -File <repo>\scripts\auto_eval.ps1" /sc hourly /st 00:00
param([string]$HengRoot = "", [string]$OutRoot = "")
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path $PSScriptRoot -Parent
if (-not $HengRoot) { $HengRoot = Join-Path (Split-Path $RepoRoot -Parent) "heng-erp" }
if (-not $OutRoot) { $OutRoot = Join-Path $RepoRoot "runs/auto" }
Set-Location $RepoRoot
$py = if (Test-Path ".venv/Scripts/python.exe") { ".venv/Scripts/python.exe" }
      elseif (Test-Path ".venv/bin/python") { ".venv/bin/python" } else { "python" }
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$out = Join-Path $OutRoot $stamp
& $py -m evalpipe heng --heng-root $HengRoot --adapter baseline --out $out --feed-evolution
if ($LASTEXITCODE -ne 0) { exit 1 }
& $py -m evalpipe gate "$out/report.json" --baseline baselines/heng_erp_baseline.json
$gate = $LASTEXITCODE
& $py -m evalpipe backflow "$out/report.json" --out "$out/backflow"
$prev = Get-ChildItem $OutRoot -Directory | Sort-Object Name | Select-Object -Last 2 | Select-Object -First 1
if ($prev -and $prev.FullName -ne $out) {
  & $py -m evalpipe drift "$($prev.FullName)/report.json" "$out/report.json"
}
Write-Host "auto-eval done: $out gate_exit=$gate"
exit $gate
