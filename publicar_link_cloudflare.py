"""Publica o endereco HTTPS no GitHub; opcionalmente gerencia o Quick Tunnel."""
import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
import requests

REPOSITORY = 'PopularAtacarejo/AgentImp'
API = f'https://api.github.com/repos/{REPOSITORY}/contents/server-url.json'


def validate_url(value):
    parsed = urlsplit(value)
    if (parsed.scheme != 'https' or not parsed.hostname or
        not re.fullmatch(r'[a-z0-9-]+\.trycloudflare\.com', parsed.hostname) or
        parsed.username or parsed.password or parsed.query or parsed.fragment or
        parsed.path not in ('', '/') or parsed.port not in (None, 443)):
        raise ValueError('Informe um HTTPS valido do trycloudflare.com.')
    return 'https://' + parsed.hostname


def publish_url(value, token):
    address = validate_url(value)
    headers = {'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
               'X-GitHub-Api-Version': '2022-11-28'}
    response = requests.get(API, headers=headers, timeout=20)
    if response.status_code != 200:
        raise RuntimeError(f'Falha ao ler arquivo no GitHub (HTTP {response.status_code}).')
    current = response.json()
    previous = json.loads(base64.b64decode(current['content']))
    if previous.get('server') == address:
        return False
    data = dict(schema=1, server=address, updated_at=datetime.now(timezone.utc).isoformat())
    response = requests.put(API, headers=headers, json={
        'message': 'Atualiza endereco HTTPS do servidor de impressoras',
        'content': base64.b64encode((json.dumps(data, indent=2)+'\n').encode()).decode(),
        'sha': current['sha'],
    }, timeout=20)
    if response.status_code != 200:
        raise RuntimeError(f'Falha ao publicar endereco no GitHub (HTTP {response.status_code}).')
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', help='Publica o link de um tunel ja iniciado')
    parser.add_argument('--origin', default='http://127.0.0.1:8007')
    args = parser.parse_args()
    token = os.environ.get('AGENTIMP_GITHUB_TOKEN', '').strip()
    if not token and os.name == 'nt':
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as key:
                token = str(winreg.QueryValueEx(key, 'AGENTIMP_GITHUB_TOKEN')[0]).strip()
        except OSError:
            pass
    if not token:
        print('Configure AGENTIMP_GITHUB_TOKEN no servidor com permissao Contents: Read and write somente no repositorio AgentImp.', file=sys.stderr)
        return 1
    process = None
    try:
        if args.url:
            publish_url(args.url, token)
            print('Endereco publicado no GitHub.', flush=True)
            return 0
        binary = shutil.which('cloudflared')
        if not binary:
            raise RuntimeError('cloudflared nao instalado no servidor.')
        logs = Path(__file__).resolve().parent / 'logs'
        logs.mkdir(exist_ok=True)
        while True:
            process = subprocess.Popen([binary, 'tunnel', '--url', args.origin, '--no-autoupdate'],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            with (logs / 'cloudflare_agentimp.log').open('a', encoding='utf-8') as log:
                for line in process.stdout:
                    log.write(line)
                    log.flush()
                    match = re.search(r'https://[a-z0-9-]+\.trycloudflare\.com', line)
                    if match:
                        for attempt in range(5):
                            try:
                                publish_url(match.group(0), token)
                                print('Novo endereco Cloudflare publicado no GitHub.', flush=True)
                                break
                            except (requests.RequestException, RuntimeError):
                                if attempt == 4:
                                    raise RuntimeError('Nao foi possivel publicar o novo link. Verifique o token e a conexao do servidor.') from None
                                time.sleep(5)
            process.wait()
            print('Tunel encerrado; reiniciando em 10 segundos.', flush=True)
            time.sleep(10)
    except KeyboardInterrupt:
        return 0
    except (ValueError, RuntimeError, requests.RequestException) as exc:
        print(f'Erro: {exc}', file=sys.stderr)
        return 1
    finally:
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == '__main__':
    raise SystemExit(main())
