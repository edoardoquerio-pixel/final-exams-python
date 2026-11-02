$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $verificationPython = Join-Path $PSScriptRoot '.venv-verifica/Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $verificationPython)) {
        throw 'Creare .venv-verifica e installare .[dev], setuptools e wheel come descritto nel README.'
    }
    function Invoke-Check {
        # Python build writes progress to stderr even when it succeeds. Under
        # Windows PowerShell, redirected stderr must not abort before exit-code validation.
        $previousErrorActionPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = 'Continue'
            & $verificationPython -B @args
            $checkExitCode = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $previousErrorActionPreference
        }
        if ($checkExitCode -ne 0) { throw "Verifica fallita: $args" }
    }
    $runDirectory = '.verification-windows-' + [guid]::NewGuid().ToString('N')
    Invoke-Check -m pytest -q -rs -p no:cacheprovider "--basetemp=$runDirectory" tests
    Invoke-Check -m ruff check --no-cache src tests smoke_release.py
    Invoke-Check -m bandit -r src/fad_downloader -q
    Invoke-Check -m pip check
    Invoke-Check -m build --no-isolation --outdir .verification-artifacts
    # A build run by a sandbox account must remain readable by the project owner.
    $projectOwner = (Get-Acl -LiteralPath 'pyproject.toml').Owner
    foreach ($packageFile in @('.verification-artifacts/fad_downloader-0.2.0-py3-none-any.whl', '.verification-artifacts/fad_downloader-0.2.0.tar.gz')) {
        & icacls $packageFile /grant "${projectOwner}:(R)"
        if ($LASTEXITCODE -ne 0) { throw 'Impossibile rendere leggibile il pacchetto al proprietario del progetto.' }
    }
    Invoke-Check -m pip install --no-index --no-deps --upgrade --target .verification-installed .verification-artifacts/fad_downloader-0.2.0-py3-none-any.whl
    $previousPythonPath = $env:PYTHONPATH
    try {
        $env:PYTHONPATH = Join-Path $PSScriptRoot '.verification-installed'
        Invoke-Check smoke_release.py
    } finally {
        $env:PYTHONPATH = $previousPythonPath
    }
} finally {
    Pop-Location
}
