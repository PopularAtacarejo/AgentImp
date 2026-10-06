"""GitHub credentials protected with Windows DPAPI, shared by panel and publisher."""
import base64
import os
import requests
from telegram_bot_config import _load, win32crypt

REPOSITORY = 'PopularAtacarejo/AgentImp'


def existing_token():
    for key in ('AGENTIMP_GITHUB_TOKEN', 'GH_TOKEN', 'GITHUB_TOKEN'):
        value = os.environ.get(key, '').strip()
        if value:
            return value
    if os.name == 'nt':
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as key:
                for name in ('AGENTIMP_GITHUB_TOKEN','GH_TOKEN','GITHUB_TOKEN'):
                    try:
                        value = str(winreg.QueryValueEx(key,name)[0]).strip()
                        if value:
                            return value
                    except OSError:
                        pass
        except OSError:
            pass
    return ''


def resolve_github_token(base_file):
    settings = _load(base_file).get('github', {})
    encoded = settings.get('protected_token')
    if encoded:
        if win32crypt is None:
            raise ValueError('Protecao de credenciais do Windows indisponivel.')
        try:
            result = win32crypt.CryptUnprotectData(base64.b64decode(encoded), None, None, None, 0)
            return (result if isinstance(result,bytes) else result[1]).decode('utf-8')
        except Exception:
            raise ValueError('Nao foi possivel abrir o token GitHub salvo. Cadastre novamente neste usuario Windows.') from None
    return existing_token()


def public_github_config(base_file):
    settings = _load(base_file).get('github', {})
    configured = bool(settings.get('protected_token') or existing_token())
    return dict(enabled=bool(settings.get('enabled', configured)), configured=configured,
                repository=REPOSITORY, path='server-url.json',
                source='Windows' if settings.get('protected_token') else 'Token existente no servidor' if configured else 'Nenhuma')


def update_github_config(data, payload):
    if not isinstance(payload,dict):
        raise ValueError('Configuracao GitHub invalida.')
    settings = dict(data.get('github') or {})
    settings['enabled'] = bool(payload.get('enabled'))
    token = str(payload.get('token') or '').strip()
    if payload.get('remove_token'):
        settings.pop('protected_token',None)
    elif token:
        if ':' in token:
            raise ValueError('Informe um token GitHub, separado do token Telegram.')
        if win32crypt is None:
            raise ValueError('Protecao de credenciais do Windows indisponivel.')
        result = win32crypt.CryptProtectData(token.encode('utf-8'),'Gerador de Placas GitHub',None,None,None,0)
        settings['protected_token'] = base64.b64encode(result if isinstance(result,bytes) else result[1]).decode('ascii')
    data['github'] = settings


def check_github_access(base_file):
    token = resolve_github_token(base_file)
    if not token:
        raise ValueError('Cadastre um token GitHub ou configure um token existente no servidor.')
    headers = {'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json'}
    try:
        response = requests.get('https://api.github.com/repos/'+REPOSITORY, headers=headers,timeout=15)
        if response.status_code != 200:
            raise ValueError(f'GitHub recusou o acesso (HTTP {response.status_code}). Verifique o token e o repositorio.')
        if response.json().get('permissions',{}).get('push') is False:
            raise ValueError('Este acesso nao permite escrita no repositorio.')
        response = requests.get('https://api.github.com/repos/'+REPOSITORY+'/contents/server-url.json',headers=headers,timeout=15)
        if response.status_code != 200:
            raise ValueError(f'Nao foi possivel ler server-url.json (HTTP {response.status_code}).')
        return {'message':'Acesso ao repositorio validado. O token precisa de Contents: Read and write para publicar o link.'}
    except requests.RequestException:
        raise ValueError('Nao foi possivel comunicar com o GitHub.') from None
