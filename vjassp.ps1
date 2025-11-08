param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $ArgsFromCaller
)

$Required = '3.12'
$Vjassp = Join-Path $PSScriptRoot 'vjassp.py'

if (-not (Test-Path $Vjassp)) {
    Write-Error "vjassp.py not found: $Vjassp"
    exit 2
}

function Get-PythonMajorMinor([string] $exePath) {
    try {
        $out = & $exePath -c 'import sys; sys.stdout.write(str(sys.version_info[0])+\".\"+str(sys.version_info[1]))' 
        return $out.Trim()
    } catch {
        return $null
    }
}

function Test-Python312([string] $exePath) {
    $mm = Get-PythonMajorMinor $exePath
    return ($mm -eq $Required)
}

$chosen = $null

# 1) Try PATH python
if (Test-Python312 'python') {
    $chosen = 'python'
}

# 2) Search recursively under current working directory if not found
if (-not $chosen) {
    Get-ChildItem -Path (Get-Location) -Recurse -File -Filter 'python.exe' -ErrorAction SilentlyContinue |
        ForEach-Object {
            Write-Host "Found Python executable: $($_.FullName)"
            if (Test-Python312 $_.FullName) {
                $chosen = $_.FullName
                break
            }
        }
}

if (-not $chosen) {
    Write-Error "Python $Required not found in PATH or under current directory."
    exit 1
}

# Run vjassp.py with the found python
& $chosen $Vjassp @ArgsFromCaller
exit $LASTEXITCODE
