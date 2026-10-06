# Descoberta do servidor de impressoras

O arquivo server-url.json guarda somente o HTTPS atual e a data de atualizacao.
Nenhuma senha, token de bot ou credencial de impressoras deve ser publicada.

Os agentes consultam a URL abaixo a cada 30 segundos. Ao mudar o endereco,
preservam a identidade e a credencial locais e reconectam automaticamente.

https://raw.githubusercontent.com/PopularAtacarejo/AgentImp/main/server-url.json

## Configurar o servidor uma vez

1. Crie um token fine-grained do GitHub com acesso apenas a este repositorio e
   permissao Contents: Read and write.
2. No servidor, execute configurar_publicacao_github.ps1 usando PowerShell.
   Ele pede o token com entrada oculta e salva AGENTIMP_GITHUB_TOKEN no usuario.
3. Reinicie o Gerador de Placas. Com a credencial configurada, o sistema inicia
   cloudflared, detecta o novo Quick Tunnel HTTPS e publica o endereco neste arquivo.
4. Instale a atualizacao do agente em cada computador, mantendo config.json.
   Execute parar.bat, aguarde encerrar e execute iniciar.bat uma vez.

O servidor precisa de cloudflared, Python e requests. O cliente nao precisa de
Python ou credenciais GitHub. A pasta do cliente deve permanecer no mesmo local.

Para publicar o link de um tunel iniciado separadamente:

    python publicar_link_cloudflare.py --url https://SEU-LINK.trycloudflare.com

Para iniciar um tunel e manter a publicacao automatica:

    python publicar_link_cloudflare.py --origin http://127.0.0.1:8007

Logs locais: logs/cloudflare_publicador.log e logs/cloudflare_agentimp.log.
Uma troca de link pode levar mais que 30 segundos por cache do GitHub ou falha
de rede. O ultimo endereco e mantido nessas falhas. Reinicio durante envio de
impressao nao repete automaticamente o trabalho; confira a fila antes de reenviar.

O campo server inicia nulo ate o primeiro link real ser publicado.
