$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
if (!(Get-Command ffmpeg -ErrorAction SilentlyContinue) -or !(Get-Command ffprobe -ErrorAction SilentlyContinue)) {
  throw 'Install FFmpeg (including ffprobe) first. See DEMO.md.'
}
if (!(Test-Path '.venv/Scripts/python.exe')) {
  py -3.12 -m venv .venv
  if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 is required.' }
  & .venv/Scripts/python.exe -m pip install -r requirements.lock
  if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
}
if (!(Test-Path 'frontend/dist/index.html')) {
  npm --prefix frontend ci
  if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
  npm --prefix frontend run build
  if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
}
& .venv/Scripts/python.exe scripts/demo_server.py --open @args
exit $LASTEXITCODE
