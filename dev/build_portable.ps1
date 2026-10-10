# Build a portable Terrarium folder you can copy onto a USB stick and run on any Windows PC.
#
#     powershell -ExecutionPolicy Bypass -File dev\build_portable.ps1
#
# Result: dist\Terrarium\  (Terrarium.exe + _internal\ + "Terrarium mini.cmd"), plus dist\Terrarium-portable.zip.
# It's a folder build (--onedir), not a single exe: a one-file exe unpacks itself into the host's %TEMP%
# every launch, while the folder build runs straight off the stick and writes nothing to the host PC.
# Screenshots (S) are saved to shots\ next to Terrarium.exe, i.e. on the stick.
# Needs uv on the build machine only; the target PC needs nothing.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    uvx --python 3.12 --with pygame-ce pyinstaller terrarium.py `
        --name Terrarium --onedir --windowed --noconfirm --clean `
        --distpath dist --workpath build\pyinstaller --specpath build
    if ($LASTEXITCODE) { throw "pyinstaller failed" }
    Set-Content -Encoding ascii dist\Terrarium\"Terrarium mini.cmd" "@start `"`" `"%~dp0Terrarium.exe`" --mini"
    Compress-Archive -Force dist\Terrarium dist\Terrarium-portable.zip
    "Built dist\Terrarium\ and dist\Terrarium-portable.zip"
} finally {
    Pop-Location
}
