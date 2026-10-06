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
    token = os.environ.get('AGENTIMP_GITHUB_TOKEN', '').strip()
    if not token:
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as key:
                token = str(winreg.QueryValueEx(key, 'AGENTIMP_GITHUB_TOKEN')[0]).strip()
        except OSError:
            pass
    if not token:
        print('[CLOUDFLARE] Publicacao automatica aguarda AGENTIMP_GITHUB_TOKEN no servidor.', flush=True)
        return
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
            def cleanup():
                if child and child.poll() is None:
                    # Encerra tambem o cloudflared pertencente a este publicador.
                    subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],
                        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NO_WINDOW)
            atexit.register(cleanup)
            with (logs / 'cloudflare_publicador.log').open('ab') as output:
                while True:
                    if child is None or child.poll() is not None:
                        child = subprocess.Popen([sys.executable,'-u',str(root/'publicar_link_cloudflare.py')],
                            cwd=root, stdout=output, stderr=output, creationflags=subprocess.CREATE_NO_WINDOW)
                    time.sleep(30)
    threading.Thread(target=worker,name='cloudflare-publicador',daemon=True).start()
