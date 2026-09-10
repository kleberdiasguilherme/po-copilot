#Requires -Version 5.1
<#
.SYNOPSIS
    Sobe a API (:8000) e o web (:3000) do PO Copilot em paralelo.

.DESCRIPTION
    Equivalente ao alvo `make dev`, para quem esta no Windows sem make.
    Ctrl+C derruba os dois processos.

    Este script so funciona a partir do M0 (14/09/2026), quando apps/api e
    apps/web passam a existir. Antes disso ele para com uma mensagem explicita.

.EXAMPLE
    .\dev.ps1
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot

$faltando = @()
if (-not (Test-Path (Join-Path $root 'apps\api'))) { $faltando += 'apps/api' }
if (-not (Test-Path (Join-Path $root 'apps\web'))) { $faltando += 'apps/web' }

if ($faltando.Count -gt 0) {
    Write-Host ''
    Write-Host '  Ambiente de dev ainda nao existe.' -ForegroundColor Yellow
    Write-Host ''
    Write-Host "  Faltando: $($faltando -join ', ')"
    Write-Host ''
    Write-Host '  Isso e esperado antes do M0. O scaffold do FastAPI e do Next.js'
    Write-Host '  e a primeira tarefa do M0, em 14/09/2026. Ate la apps/ fica vazio'
    Write-Host '  de proposito e este script nao tem o que subir.'
    Write-Host ''
    Write-Host '  Veja docs/roadmap.md para o que entra em cada milestone.'
    Write-Host ''
    exit 1
}

$procs = @()

try {
    Write-Host '-> API  em http://localhost:8000' -ForegroundColor Cyan
    $procs += Start-Process -FilePath 'python' `
        -ArgumentList '-m', 'uvicorn', 'app.main:app', '--reload', '--port', '8000' `
        -WorkingDirectory (Join-Path $root 'apps\api') `
        -NoNewWindow -PassThru

    Write-Host '-> Web  em http://localhost:3000' -ForegroundColor Cyan
    $procs += Start-Process -FilePath 'npm' `
        -ArgumentList 'run', 'dev' `
        -WorkingDirectory (Join-Path $root 'apps\web') `
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
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
        }
    }
}
