$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$frontendDirectory = Join-Path $projectRoot 'frontend'
$packageJson = Join-Path $frontendDirectory 'package.json'
$approvedEnvironment = @{
    FITTRACK_TEST_DB_NAME = 'fittrack_test_20261116_a91f'
    FITTRACK_TEST_DB_HOST = '127.0.0.1'
    FITTRACK_TEST_DB_USER = 'ft_test_20261116_a91f'
    FITTRACK_TEST_DB_CONFIRM = 'I_CONFIRM_THIS_IS_A_DISPOSABLE_TEST_DATABASE'
    FITTRACK_RUN_DB_TESTS = '1'
}

if (-not (Test-Path -LiteralPath $packageJson -PathType Leaf)) {
    [Console]::Error.WriteLine('FitTrack E2E launcher could not locate frontend/package.json.')
    exit 1
}

$npmCommand = Get-Command 'npm.cmd' -ErrorAction SilentlyContinue
if (-not $npmCommand) {
    [Console]::Error.WriteLine('FitTrack E2E launcher requires npm.cmd on PATH.')
    exit 1
}

$securePassword = $null
$plainPassword = $null
$passwordPointer = [IntPtr]::Zero
$playwrightExitCode = 1
$locationPushed = $false

try {
    Push-Location -LiteralPath $frontendDirectory
    $locationPushed = $true
    $securePassword = Read-Host 'Disposable FitTrack MySQL test password' -AsSecureString
    if ($null -eq $securePassword -or $securePassword.Length -eq 0) {
        throw 'A non-empty disposable test password is required.'
    }

    foreach ($name in $approvedEnvironment.Keys) {
        Set-Item -Path "Env:$name" -Value $approvedEnvironment[$name]
    }

    $passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
    $plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)
    $env:FITTRACK_TEST_DB_PASSWORD = $plainPassword

    & npm.cmd run test:e2e
    if ($null -ne $LASTEXITCODE) {
        $playwrightExitCode = $LASTEXITCODE
    }
}
catch {
    [Console]::Error.WriteLine('FitTrack E2E launcher failed before Playwright completed. Review non-secret error output above.')
    $playwrightExitCode = 1
}
finally {
    foreach ($name in $approvedEnvironment.Keys) {
        Remove-Item -Path "Env:$name" -ErrorAction SilentlyContinue
    }
    Remove-Item -Path 'Env:FITTRACK_TEST_DB_PASSWORD' -ErrorAction SilentlyContinue

    if ($passwordPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
    }
    if ($null -ne $securePassword) {
        $securePassword.Dispose()
    }
    $plainPassword = $null
    $securePassword = $null
    if ($locationPushed) {
        Pop-Location -ErrorAction SilentlyContinue
    }
}

Write-Host ("Playwright exit code: {0}" -f $playwrightExitCode)
exit $playwrightExitCode
