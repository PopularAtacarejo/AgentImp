"""Telegram settings with a Windows-protected bot credential."""
import base64
import json
import os
import re
from pathlib import Path

try:
    import win32crypt
except ImportError:
    win32crypt = None


def _path(base_file):
    return Path(base_file).resolve().parent / "dados" / "telegram_product_bot.json"


def _load(base_file):
    path = _path(base_file)
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Configuração do Telegram inválida.")
    return data


def resolve_token(base_file):
    data = _load(base_file)
    encoded = data.get("protected_token")
    if encoded:
        if win32crypt is None:
            raise ValueError("A proteção de tokens do Windows não está disponível.")
        try:
            result = win32crypt.CryptUnprotectData(base64.b64decode(encoded), None, None, None, 0)
            return (result if isinstance(result, bytes) else result[1]).decode("utf-8")
        except Exception as exc:
            raise ValueError("Não foi possível abrir o token salvo. Cadastre-o novamente neste usuário do Windows.") from exc
    return os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()


def public_config(base_file):
    data = _load(base_file)
    from github_link_config import public_github_config
    github = public_github_config(base_file)
    saved = bool(data.get("protected_token"))
    configured = saved or bool(os.environ.get("TELEGRAM_BOT_TOKEN", "").strip())
    return {"configured": configured, "source": "Windows" if saved else "Variável de ambiente" if configured else "Nenhuma",
            "masked": "", "github": github, "users": [{"telegram_id": str(key), "username": value} for key, value in (data.get("users") or {}).items()]}


def save_config(base_file, payload):
    if not isinstance(payload, dict):
        raise ValueError("Configuração inválida.")
    data = _load(base_file)
    rows = payload.get("users", [])
    if not isinstance(rows, list):
        raise ValueError("Lista de usuários inválida.")
    users = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Usuário inválido.")
        raw_id = str(row.get("telegram_id") or "").strip()
        username = str(row.get("username") or "").strip()
        if not raw_id and not username:
            continue
        if not raw_id.isascii() or not raw_id.isdigit() or int(raw_id) <= 0 or not username:
            raise ValueError("Informe um ID Telegram positivo e o usuário do sistema em cada linha.")
        key = str(int(raw_id))
        if key in users:
            raise ValueError("O mesmo ID Telegram foi informado mais de uma vez.")
        users[key] = username
    token = str(payload.get("token") or "").strip()
    if payload.get("remove_token"):
        data.pop("protected_token", None)
    elif token:
        if not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]{20,}", token):
            raise ValueError("Token inválido. Copie o token completo fornecido pelo BotFather.")
        if win32crypt is None:
            raise ValueError("A proteção de tokens do Windows não está disponível.")
        try:
            result = win32crypt.CryptProtectData(token.encode("utf-8"), "Gerador de Placas Telegram", None, None, None, 0)
            data["protected_token"] = base64.b64encode(result if isinstance(result, bytes) else result[1]).decode("ascii")
        except Exception as exc:
            raise ValueError("Não foi possível proteger o token no Windows.") from exc
    if "github" in payload:
        from github_link_config import update_github_config
        update_github_config(data, payload["github"])
    data["users"] = users
    path = _path(base_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    return public_config(base_file)
