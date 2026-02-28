param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Args
)

$ErrorActionPreference = "Stop"
.\.venv\Scripts\Activate.ps1

pm export @Args