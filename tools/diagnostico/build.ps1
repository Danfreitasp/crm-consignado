$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

Write-Host "Gerando mapa de versoes conhecidas..."
python gerar_versoes.py

Write-Host "Gerando executavel com PyInstaller..."
python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --console `
    --noupx `
    --name crm-diagnostico `
    --distpath dist `
    --workpath build `
    --specpath . `
    --add-data "versoes_conhecidas.json;." `
    diagnostico.py

Copy-Item "COMO-USAR.txt" "dist\COMO-USAR.txt" -Force

$zip = "dist\crm-diagnostico.zip"
if (Test-Path $zip) {
    Remove-Item $zip -Force
}
Compress-Archive -Path "dist\crm-diagnostico.exe", "dist\COMO-USAR.txt" -DestinationPath $zip

Write-Host ""
Write-Host "Gerado:"
Get-Item "dist\crm-diagnostico.exe", $zip | Select-Object FullName, Length
