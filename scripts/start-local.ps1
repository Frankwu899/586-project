$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
if (!(Get-Command ffmpeg -ErrorAction SilentlyContinue) -or !(Get-Command ffprobe -ErrorAction SilentlyContinue)) {
  throw 'FFmpeg is required. Install FFmpeg with ffprobe on PATH, then reopen this launcher. See LOCAL_API.md.'
}
if (!(Test-Path '.venv/Scripts/python.exe')) {
  py -3.12 -m venv .venv
  if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.12 with the Python launcher, then reopen this launcher.' }
}
& .venv/Scripts/python.exe -c 'import sys; assert sys.version_info[:2] == (3, 12), "Use Python 3.12 in a fresh extracted bundle."'
if ($LASTEXITCODE -ne 0) { throw 'Python version check failed.' }
$localLockHash = (Get-FileHash requirements.lock -Algorithm SHA256).Hash
if (!(Test-Path '.venv/local-install.sha256') -or (Get-Content '.venv/local-install.sha256' -Raw) -ne $localLockHash) {
  & .venv/Scripts/python.exe -m pip install -r requirements.lock
  if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed; reopen the launcher to retry.' }
  Set-Content '.venv/local-install.sha256' $localLockHash -NoNewline
}
if (!(Test-Path 'frontend/dist/index.html')) {
  npm --prefix frontend ci
  if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
  npm --prefix frontend run build
  if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
}
& .venv/Scripts/python.exe scripts/local_server.py @args
exit $LASTEXITCODE
