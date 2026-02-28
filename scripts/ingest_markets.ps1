param(
    [int]$EventId = 0,
    [int]$Pages = 1,
    [int]$Limit = 1000
)

$ErrorActionPreference = "Stop"
.\.venv\Scripts\Activate.ps1

$cliArgs = @("ingest-markets", "--pages", "$Pages", "--limit", "$Limit")
if ($EventId -ne 0) { $cliArgs += @("--event-id", "$EventId") }

pm @cliArgs