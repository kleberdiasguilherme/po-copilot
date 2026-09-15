#Requires -Version 5.1
<#
.SYNOPSIS
    Sobe a API (:8000) e o web (:3000) do PO Copilot em paralelo.

.DESCRIPTION
    Equivalente ao alvo `make dev`, para quem esta no Windows sem make.
    Ctrl+C derruba os dois processos.

.EXAMPLE
    .\dev.ps1
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot

$apiDir = Join-Path $root 'apps\api'
$webDir = Join-Path $root 'apps\web'

$faltando = @()
if (-not (Test-Path $apiDir)) { $faltando += 'apps/api' }
if (-not (Test-Path $webDir)) { $faltando += 'apps/web' }

if ($faltando.Count -gt 0) {
    Write-Host ''
    Write-Host '  Scaffold ausente.' -ForegroundColor Yellow
    Write-Host ''
    Write-Host "  Faltando: $($faltando -join ', ')"
    Write-Host ''
    Write-Host '  Veja docs/roadmap.md para o que entra em cada milestone.'
    Write-Host ''
    exit 1
}

# A API roda com o Python do venv. Sem ele, o fastapi/uvicorn nao existe.
$venvPython = Join-Path $apiDir '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPython)) {
    Write-Host ''
    Write-Host '  O venv da API ainda nao existe.' -ForegroundColor Yellow
    Write-Host ''
    Write-Host '  Rode uma vez, a partir da raiz do repo:'
    Write-Host ''
    Write-Host '    python -m venv apps/api/.venv'
    Write-Host '    apps/api/.venv/Scripts/python.exe -m pip install -r apps/api/requirements.txt'
    Write-Host ''
    exit 1
}

if (-not (Test-Path (Join-Path $webDir 'node_modules'))) {
    Write-Host ''
    Write-Host '  As dependencias do web ainda nao foram instaladas.' -ForegroundColor Yellow
    Write-Host ''
    Write-Host '  Rode: cd apps/web; npm install'
    Write-Host ''
    exit 1
}

$procs = @()

try {
    Write-Host '-> API  em http://localhost:8000' -ForegroundColor Cyan
    $procs += Start-Process -FilePath $venvPython `
        -ArgumentList '-m', 'uvicorn', 'app.main:app', '--reload', '--port', '8000' `
        -WorkingDirectory $apiDir `
        -NoNewWindow -PassThru

    Write-Host '-> Web  em http://localhost:3000' -ForegroundColor Cyan
    $procs += Start-Process -FilePath 'cmd.exe' `
        -ArgumentList '/c', 'npm', 'run', 'dev' `
        -WorkingDirectory $webDir `
        -NoNewWindow -PassThru

    Write-Host ''
    Write-Host 'Ctrl+C para parar os dois.' -ForegroundColor DarkGray
    Write-Host ''

    while ($true) {
        foreach ($p in $procs) {
            if ($p.HasExited) {
                Write-Host ''
                Write-Host "Processo $($p.ProcessName) (PID $($p.Id)) saiu com codigo $($p.ExitCode). Derrubando o outro." -ForegroundColor Yellow
                return
            }
        }
        Start-Sleep -Milliseconds 400
    }
}
finally {
    foreach ($p in $procs) {
        if ($p -and -not $p.HasExited) {
            # /T derruba os filhos: o reloader do uvicorn e o next dev sob o cmd.
            & taskkill.exe /PID $p.Id /T /F 2>&1 | Out-Null
        }
    }
}
