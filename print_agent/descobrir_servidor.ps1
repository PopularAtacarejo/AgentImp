# Resolve somente dados JSON de um repositorio conhecido; nunca executa codigo baixado.
function Update-ServerAddress($Config, [string]$ConfigPath) {
    $now = [DateTime]::UtcNow
    if ($script:nextDiscovery -and $now -lt $script:nextDiscovery) { return }
    $script:nextDiscovery = $now.AddSeconds(30)
    try {
        $endpoint = 'https://raw.githubusercontent.com/PopularAtacarejo/AgentImp/main/server-url.json?t=' + $now.Ticks
        $response = Invoke-WebRequest -UseBasicParsing -Uri $endpoint -Headers @{'User-Agent'='PopularAtacarejo-PrintAgent';'Cache-Control'='no-cache'} -TimeoutSec 8 -MaximumRedirection 0
        if ($response.Content.Length -gt 4096) { throw 'Arquivo de descoberta invalido.' }
        $data = $response.Content | ConvertFrom-Json
        if ($data.schema -ne 1 -or -not $data.server) { return }
        $url = [Uri][string]$data.server
        if (-not $url.IsAbsoluteUri -or $url.Scheme -ne 'https' -or $url.Host -notmatch '^[a-z0-9-]+\.trycloudflare\.com$' -or $url.UserInfo -or $url.Query -or $url.Fragment -or $url.AbsolutePath -ne '/' -or $url.Port -ne 443) {
            throw 'Endereco Cloudflare invalido.'
        }
        $address = $url.GetLeftPart([UriPartial]::Authority)
        if ($Config.server.TrimEnd('/') -ne $address) {
            $old = $Config.server
            $Config.server = $address
            try {
                $Config | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath ($ConfigPath + '.tmp') -Encoding UTF8
                Move-Item -LiteralPath ($ConfigPath + '.tmp') -Destination $ConfigPath -Force
            } catch {
                $Config.server = $old
                throw
            }
            Write-Log 'Endereco Cloudflare atualizado automaticamente pelo GitHub.'
        }
    } catch {
        # Mantem a configuracao funcional se GitHub estiver indisponivel.
        $script:nextDiscovery = $now.AddSeconds(60)
        Write-Log 'Nao foi possivel consultar o endereco no GitHub; mantendo o ultimo endereco.'
    }
}
