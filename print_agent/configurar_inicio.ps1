param([switch]$DisableStartup)
$ErrorActionPreference = 'Stop'
try {
    $root = $PSScriptRoot
    $agent = Join-Path $root 'agente.ps1'
    $configPath = Join-Path $root 'config.json'
    $config = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ([string]$config.agent_id -notmatch '^[a-f0-9]{32}$') { throw 'Configuracao invalida. Extraia o pacote completo antes de iniciar.' }
    $startup = [Environment]::GetFolderPath('Startup')
    $shortcutPath = Join-Path $startup ('Placas-Impressoras-' + $config.agent_id + '.lnk')
    if ($DisableStartup) {
        if (Test-Path -LiteralPath $shortcutPath) { Remove-Item -LiteralPath $shortcutPath }
        Write-Host 'Inicio automatico desativado. Para encerrar agora, execute parar.bat.'
        exit 0
    }
    if (-not (Test-Path -LiteralPath $agent)) { throw 'agente.ps1 nao encontrado. Extraia todos os arquivos do ZIP.' }
    $powershell = Join-Path $PSHOME 'powershell.exe'
    $arguments = '-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $agent + '"'
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $powershell
    $shortcut.Arguments = $arguments
    $shortcut.WorkingDirectory = $root
    $shortcut.WindowStyle = 7
    $shortcut.Description = 'Agente de impressoras do Gerador de Placas'
    $shortcut.Save()
    Start-Process -FilePath $powershell -ArgumentList $arguments -WorkingDirectory $root -WindowStyle Hidden
    Write-Host 'Agente iniciado. Inicio automatico configurado para este usuario do Windows.'
    Write-Host 'Mantenha esta pasta no mesmo local. Confira a conexao no painel e os detalhes em agente.log.'
} catch {
    Write-Host ('Falha: ' + $_.Exception.Message)
    exit 1
}
