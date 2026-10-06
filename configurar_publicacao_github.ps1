$ErrorActionPreference = 'Stop'
Write-Host 'Crie um token GitHub com acesso somente a PopularAtacarejo/AgentImp e Contents: Read and write.'
Write-Host 'O token sera salvo na variavel de ambiente do usuario Windows deste servidor.'
$secret = Read-Host 'Cole o token (entrada oculta)' -AsSecureString
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
try {
    $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer).Trim()
    if (-not $token) { throw 'Token vazio.' }
    [Environment]::SetEnvironmentVariable('AGENTIMP_GITHUB_TOKEN', $token, 'User')
    Write-Host 'Configurado. Feche e abra o sistema para iniciar o tunel e publicar o link automaticamente.'
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    $token = $null
}
