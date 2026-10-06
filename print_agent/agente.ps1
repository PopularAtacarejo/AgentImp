# Windows PowerShell 5.1 / Windows 10+. No third-party dependencies.
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$log = Join-Path $root 'agente.log'
$journal = Join-Path $root 'ultimo-envio.json'
$stopFile = Join-Path $root 'parar.sinal'
. (Join-Path $root 'descobrir_servidor.ps1')
function Write-Log([string]$Message) {
    if ((Test-Path -LiteralPath $log) -and (Get-Item -LiteralPath $log).Length -gt 1048576) {
        Move-Item -LiteralPath $log -Destination ($log + '.anterior') -Force
    }
    Add-Content -LiteralPath $log -Value ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $Message) -Encoding UTF8
}
function Save-Result($Value) {
    $Value | ConvertTo-Json -Depth 6 -Compress | Set-Content -LiteralPath ($journal + '.tmp') -Encoding UTF8
    Move-Item -LiteralPath ($journal + '.tmp') -Destination $journal -Force
}
function Print-Label($Job) {
    if ($Job.copies -lt 1 -or $Job.copies -gt 20 -or $Job.width_mm -lt 40 -or $Job.width_mm -gt 104 -or $Job.height_mm -lt 25 -or $Job.height_mm -gt 100) {
        throw 'Medidas ou quantidade invalidas.'
    }
    if ([string]$Job.image -notmatch '^[A-Za-z0-9+/=]+$' -or $Job.image.Length -gt 2097152) { throw 'Imagem invalida.' }
    $bytes = [Convert]::FromBase64String($Job.image)
    $stream = New-Object IO.MemoryStream(,$bytes)
    $image = $null
    $document = New-Object System.Drawing.Printing.PrintDocument
    try {
        $image = [System.Drawing.Image]::FromStream($stream)
        if ($image.Width -gt 2000 -or $image.Height -gt 2000) { throw 'Imagem excede o limite.' }
        $document.PrinterSettings.PrinterName = [string]$Job.printer
        $document.PrinterSettings.Copies = 1
        if (-not $document.PrinterSettings.IsValid) { throw 'Impressora nao instalada ou indisponivel.' }
        $document.DocumentName = 'Etiqueta ' + $Job.id
        $document.PrintController = New-Object System.Drawing.Printing.StandardPrintController
        $width = [int][Math]::Round([double]$Job.width_mm / 25.4 * 100)
        $height = [int][Math]::Round([double]$Job.height_mm / 25.4 * 100)
        $document.DefaultPageSettings.PaperSize = New-Object System.Drawing.Printing.PaperSize('Etiqueta', $width, $height)
        $document.DefaultPageSettings.Margins = New-Object System.Drawing.Printing.Margins(0,0,0,0)
        $document.DefaultPageSettings.Landscape = $false
        $pageState = @{left = [int]$Job.copies}
        $handler = {
            param($sender, $eventArgs)
            $eventArgs.Graphics.TranslateTransform(-$eventArgs.PageSettings.HardMarginX, -$eventArgs.PageSettings.HardMarginY)
            $eventArgs.Graphics.DrawImage($image, [System.Drawing.RectangleF]::new(0,0,$width,$height))
            $pageState.left--
            $eventArgs.HasMorePages = $pageState.left -gt 0
        }.GetNewClosure()
        $document.add_PrintPage($handler)
        $document.Print()
    } finally {
        $document.Dispose()
        if ($null -ne $image) { $image.Dispose() }
        $stream.Dispose()
    }
}
$mutex = $null
$acquired = $false
try {
    $config = Get-Content -LiteralPath (Join-Path $root 'config.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if ([string]$config.agent_id -notmatch '^[a-f0-9]{32}$') { throw 'Configuracao de agente invalida.' }
    $mutex = New-Object Threading.Mutex($false, ('Local\PlacasAgent-' + $config.agent_id))
    try { $acquired = $mutex.WaitOne(0) } catch [Threading.AbandonedMutexException] { $acquired = $true }
    if (-not $acquired) { exit }
    if (Test-Path -LiteralPath $stopFile) { Remove-Item -LiteralPath $stopFile }
    Add-Type -AssemblyName System.Drawing
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $headers = @{ Authorization = 'Bearer ' + $config.token }
    $pending = $null
    if (Test-Path -LiteralPath $journal) {
        $pending = Get-Content -LiteralPath $journal -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($pending.state -eq 'started') {
            $pending.state = 'uncertain'
            $pending.message = 'Agente interrompido durante envio. Confira a impressora.'
            Save-Result $pending
        }
    }
    Write-Log 'Agente iniciado. Aguardando trabalhos.'
    while (-not (Test-Path -LiteralPath $stopFile)) {
        Update-ServerAddress $config (Join-Path $root 'config.json')
        try {
            $printerError = ''
            $printers = @()
            try {
                $default = (New-Object System.Drawing.Printing.PrinterSettings).PrinterName
                $printers = @([System.Drawing.Printing.PrinterSettings]::InstalledPrinters | ForEach-Object {
                    @{name=[string]$_; default=($_ -eq $default); status='Instalada no Windows'}
                })
            } catch { $printerError = 'Nao foi possivel listar as impressoras. Verifique o spooler do Windows.' }
            $payload = @{agent_id=$config.agent_id; computer=$env:COMPUTERNAME; printers=$printers; error=$printerError; result=$pending}
            $json = $payload | ConvertTo-Json -Depth 8 -Compress
            $response = Invoke-RestMethod -Uri ($config.server.TrimEnd('/') + '/api/print-agent/poll') -Method Post -Headers $headers -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($json)) -TimeoutSec 20 -MaximumRedirection 0
            if (-not $response.ok) { throw 'Resposta invalida do servidor.' }
            $previousId = if ($null -ne $pending) { $pending.id } else { '' }
            $previousResult = $pending
            $pending = $null
            if (Test-Path -LiteralPath $journal) { Remove-Item -LiteralPath $journal }
            if ($null -ne $response.job) {
                $job = $response.job
                if ($job.id -eq $previousId) {
                    $pending = $previousResult
                } else {
                    $pending = @{id=$job.id;state='started';message='Envio iniciado.'}
                    Save-Result $pending  # Persist BEFORE spool submission; never blindly retry.
                    try {
                        Print-Label $job
                        $pending.state = 'spooled'
                        $pending.message = 'Enviado ao spooler do Windows. Confira a saida fisica.'
                        Write-Log ('Trabalho ' + $job.id + ' enviado ao spooler.')
                    } catch {
                        $pending.state = 'uncertain'
                        $pending.message = 'Envio nao confirmado. Confira o papel, o driver e a fila do Windows.'
                        Write-Log ('Trabalho ' + $job.id + ': ' + $_.Exception.Message)
                    }
                }
                Save-Result $pending
            }
        } catch {
            Write-Log ('Falha de comunicacao: ' + $_.Exception.Message)
            if ($_.Exception.Response -and [int]$_.Exception.Response.StatusCode -eq 401) {
                Write-Log 'Acesso revogado ou credencial invalida. Gere um novo pacote no painel.'
                break
            }
        }
        for ($i=0; $i -lt 5 -and -not (Test-Path -LiteralPath $stopFile); $i++) { Start-Sleep -Seconds 1 }
    }
    Write-Log 'Agente parado pelo usuario.'
} catch { Write-Log ('Falha ao iniciar: ' + $_.Exception.Message) }
finally {
    if ($acquired) { $mutex.ReleaseMutex() }
    if ($null -ne $mutex) { $mutex.Dispose() }
}
