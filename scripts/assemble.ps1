# Assemble the clean Projects\bluhands monorepo (Windows / PowerShell).
# Idempotent. Excludes .venv, node_modules, __pycache__, .git, build artifacts.
# Copies the working pieces from SDK\ + your customized OpenHands\frontend.
# Nothing is deleted from the OpenHands clone — frontend is COPIED out.

$ErrorActionPreference = "Stop"

$SDK  = "C:\Users\Admin\Documents\Work\Bucket\bluhandsdk\SDK"
$OH   = "C:\Users\Admin\Documents\Work\Projects\OpenHands"
$DEST = "C:\Users\Admin\Documents\Work\Projects\bluhands"

$XD = @(".venv","node_modules","__pycache__",".git",".pytest_cache",".ruff_cache",
        ".mypy_cache","build","dist",".react-router",".turbo",".next")
$XF = @("*.pyc","*.log")

function Copy-Tree($src, $dst) {
  if (-not (Test-Path $src)) { Write-Host "skip (missing): $src" -ForegroundColor Yellow; return }
  Write-Host "copy: $src -> $dst" -ForegroundColor Cyan
  robocopy $src $dst /E /XD $XD /XF $XF /NFL /NDL /NJH /NJS /NP | Out-Null
  if ($LASTEXITCODE -ge 8) { throw "robocopy failed ($LASTEXITCODE): $src" }
}

New-Item -ItemType Directory -Force -Path $DEST, "$DEST\docs" | Out-Null

Copy-Tree "$SDK\control-plane"  "$DEST\control-plane"
Copy-Tree "$SDK\bluhands-agent" "$DEST\agent"
Copy-Tree "$SDK\apps"           "$DEST\apps"
Copy-Tree "$SDK\catalog"        "$DEST\backends"
Copy-Tree "$OH\frontend"        "$DEST\frontend"

foreach ($f in @("PROJECT-HANDOFF.md","TASKS.md","WORKLOG.md")) {
  if (Test-Path "$SDK\$f") { Copy-Item "$SDK\$f" "$DEST\docs\$f" -Force }
}
if (Test-Path "$SDK\prompts") { Copy-Tree "$SDK\prompts" "$DEST\docs\prompts" }

Write-Host "`nDone. Clean monorepo at $DEST" -ForegroundColor Green
Write-Host "Next: see docs\EXTRACTION-PLAN.md -> T-A09 (wire frontend to REST backend)."
