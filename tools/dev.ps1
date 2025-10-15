# How to use: 

# pwsh tools/dev.ps1 etl
# pwsh tools/dev.ps1 test
# pwsh tools/dev.ps1 app


param([ValidateSet("etl","snap","test","app")][string]$task="etl")

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $root "..")

switch ($task) {
  "etl"  { python -m src.etl.clean_transform --input data/raw/MaineDMR_Modern_Landings_Data_2025-10-13.csv --outdir data/processed --verbose }
  "snap" { python -m seeds.snapshot }
  "test" { pytest -q }
  "app"  { streamlit run app.py }
}
