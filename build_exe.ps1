param(
  [switch]$Clean
)

if ($Clean) {
  if (Test-Path dist) { Remove-Item -Recurse -Force dist }
  if (Test-Path build) { Remove-Item -Recurse -Force build }
}

python -m pip install --quiet pyinstaller
pyinstaller --noconfirm --onefile --windowed --name BuscadorDuplo desktop.py

Write-Host "Executável gerado em dist/BuscadorDuplo.exe"

