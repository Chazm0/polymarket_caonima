param(
  [Parameter(Mandatory=$true)][string]$Session,
  [Parameter(Mandatory=$true)][string]$MarketIdsCsv
)

$ErrorActionPreference = "Stop"
.\.venv\Scripts\Activate.ps1

pm track-markets --session $Session --market-ids $MarketIdsCsv