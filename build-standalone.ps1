$ErrorActionPreference = 'Stop'
$ProjectRoot = $PSScriptRoot
$Python = Get-Command python -ErrorAction Stop

Push-Location $ProjectRoot
try {
    & $Python.Source .\create_icon.py
    & $Python.Source -m PyInstaller --version 2>$null
    if ($LASTEXITCODE -ne 0) {
        & $Python.Source -m pip install --upgrade pyinstaller
    }
    & $Python.Source -m PyInstaller --noconfirm --clean --onefile --windowed `
        --name Aster-AI-Desktop --icon .\aster.ico .\aster_ai.pyw
    Write-Host "Built: $ProjectRoot\dist\Aster-AI-Desktop.exe"
}
finally {
    Pop-Location
}
