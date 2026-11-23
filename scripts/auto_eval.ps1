# 自动巡检（可挂 Windows 任务计划程序）：跑 ERP 评测 → 门禁 → 回流+注入进化池 → 漂移
# 注册示例（每小时）:
#   schtasks /create /tn "HengERP-AutoEval" /tr "powershell -NoProfile -File D:\codex\eval-pipeline\scripts\auto_eval.ps1" /sc hourly /st 00:00
param([string]$HengRoot = "D:\codex\heng-erp", [string]$OutRoot = "D:\codex\eval-pipeline\runs\auto")
$ErrorActionPreference = "Stop"
Set-Location D:\codex\eval-pipeline
$py = ".venv\Scripts\python.exe"
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$out = Join-Path $OutRoot $stamp
& $py -m evalpipe heng --heng-root $HengRoot --adapter baseline --out $out --feed-evolution
if ($LASTEXITCODE -ne 0) { exit 1 }
& $py -m evalpipe gate "$out\report.json" --baseline baselines\heng_erp_baseline.json
$gate = $LASTEXITCODE
& $py -m evalpipe backflow "$out\report.json" --out "$out\backflow"
$prev = Get-ChildItem $OutRoot -Directory | Sort-Object Name | Select-Object -Last 2 | Select-Object -First 1
if ($prev -and $prev.FullName -ne $out) {
  & $py -m evalpipe drift "$($prev.FullName)\report.json" "$out\report.json"
}
Write-Host "auto-eval done: $out gate_exit=$gate"
exit $gate
