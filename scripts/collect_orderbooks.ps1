param(
    [int]$Batch = 0,
    [int]$TopN = 0,
    [double]$LoopSeconds = 0,
    [double]$PerBatchSleep = 0.1,
    [int]$Iterations = 0
)

$ErrorActionPreference = "Stop"
.\.venv\Scripts\Activate.ps1

$cliArgs = @("collect-orderbooks", "--per-batch-sleep", "$PerBatchSleep", "--iterations", "$Iterations")
if ($Batch -ne 0) { $cliArgs += @("--batch", "$Batch") }
if ($TopN -ne 0) { $cliArgs += @("--top-n", "$TopN") }
if ($LoopSeconds -ne 0) { $cliArgs += @("--loop-seconds", "$LoopSeconds") }

pm @cliArgs