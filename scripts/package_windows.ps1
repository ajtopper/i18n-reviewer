# Optional Windows build, self-test, portable ZIP, and optional Inno Setup script
param(
    [string]$Version = "0.1.0",
    [switch]$SkipBuild,
    [switch]$BuildInstaller
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$StdOutLog = Join-Path $env:TEMP "i18n-reviewer-selftest-out-$PID.txt"
$StdErrLog = Join-Path $env:TEMP "i18n-reviewer-selftest-err-$PID.txt"
Push-Location $RepoRoot

try {
    $PyInstaller = Join-Path $RepoRoot ".venv\Scripts\pyinstaller.exe"
    $DistDir = Join-Path $RepoRoot "dist\i18n-reviewer"
    $ExePath = Join-Path $DistDir "i18n-reviewer.exe"
    $ZipPath = Join-Path $RepoRoot "dist\i18n-reviewer-$Version-win64.zip"

    if (-not $SkipBuild) {
        if (-not (Test-Path $PyInstaller)) {
            throw "PyInstaller executable not found at $PyInstaller. Install requirements-dev.txt first."
        }
        Write-Host "Building i18n-reviewer via PyInstaller..."
        & $PyInstaller --clean -y "spec\build.spec"
        if ($LASTEXITCODE -ne 0) {
            throw "PyInstaller failed with exit code $LASTEXITCODE"
        }
    }

    if (-not (Test-Path $ExePath)) {
        throw "Frozen executable not found at $ExePath"
    }

    Write-Host "Running frozen executable --self-test..."
    $Proc = Start-Process -FilePath $ExePath -ArgumentList "--self-test" -NoNewWindow -Wait -PassThru -RedirectStandardOutput $StdOutLog -RedirectStandardError $StdErrLog
    if (Test-Path $StdOutLog) { Get-Content $StdOutLog }
    if (Test-Path $StdErrLog) { Get-Content $StdErrLog }
    if ($Proc.ExitCode -ne 0) {
        throw "Frozen --self-test failed with exit code $($Proc.ExitCode)"
    }

    if (Test-Path $ZipPath) {
        Remove-Item $ZipPath -Force
    }
    Write-Host "Creating portable ZIP archive at $ZipPath..."
    Compress-Archive -Path $DistDir -DestinationPath $ZipPath -CompressionLevel Optimal

    if ($BuildInstaller) {
        $Iscc = Get-Command iscc -ErrorAction SilentlyContinue
        if ($null -eq $Iscc) {
            throw "Inno Setup (iscc.exe) not found in PATH while -BuildInstaller was specified."
        }
        & $Iscc.Source "/DMyAppVersion=$Version" "installer\i18n-reviewer.iss"
        if ($LASTEXITCODE -ne 0) {
            throw "Inno Setup failed with exit code $LASTEXITCODE"
        }
    }
}
finally {
    Remove-Item $StdOutLog, $StdErrLog -ErrorAction SilentlyContinue
    Pop-Location
}
