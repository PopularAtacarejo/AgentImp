"""Inicia o tunel e o publicador quando a credencial local esta configurada."""
import atexit
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

_started = False
_guard = threading.Lock()


def start_cloudflare_publisher(base_file):
    global _started
    with _guard:
        if _started:
            return
        _started = True
    from communication_status import set_status
    root = Path(base_file).resolve().parent

    def worker():
        import msvcrt
        runtime = root / 'runtime'
        runtime.mkdir(exist_ok=True)
        with (runtime / 'cloudflare_publisher.lock').open('a+b') as lock:
            if lock.seek(0,2) == 0:
                lock.write(b'0')
                lock.flush()
            lock.seek(0)
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK,1)
            except OSError:
                return
            logs = root / 'logs'
            logs.mkdir(exist_ok=True)
            child = None
            active_token = None
            def cleanup():
                if child and child.poll() is None:
                    # Encerra tambem o cloudflared pertencente a este publicador.
                    subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],
                        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NO_WINDOW)
            atexit.register(cleanup)
            with (logs / 'cloudflare_publicador.log').open('ab') as output:
                while True:
                    from github_link_config import public_github_config, resolve_github_token
                    try:
                        settings = public_github_config(base_file)
                        token = resolve_github_token(base_file) if settings['enabled'] else ''
                    except (ValueError, OSError):
                        token = ''
                    if child and child.poll() is None and (not token or token != active_token):
                        cleanup()
                        child.wait(timeout=10)
                        child = None
                    if not token:
                        set_status(base_file, "cloudflare", "waiting", "Aguardando token GitHub e ativacao da publicacao automatica; nenhum novo HTTPS gerado.")
                        time.sleep(10)
                        continue
                    if child is None or child.poll() is not None:
                        set_status(base_file, "cloudflare", "connecting", "Gerando novo HTTPS do Cloudflare para comunicacao com as impressoras...")
                        active_token = token
                        child = subprocess.Popen([sys.executable,'-u',str(root/'publicar_link_cloudflare.py')],
                            cwd=root, stdout=output, stderr=output, creationflags=subprocess.CREATE_NO_WINDOW)
                    time.sleep(30)
    threading.Thread(target=worker,name='cloudflare-publicador',daemon=True).start()
