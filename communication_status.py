"""Public communication status, without tokens or product/user message contents."""
import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path

_started = False
_guard = threading.Lock()


def set_status(base_file, service, state, message, url='', bot=''):
    if service not in {'telegram','cloudflare'}:
        raise ValueError('Servico invalido.')
    root = Path(base_file).resolve().parent / 'runtime'
    root.mkdir(exist_ok=True)
    data = dict(state=state,message=message,url=url,bot=bot,updated_at=time.time(),pid=os.getpid())
    path = root / (service + '_status.json')
    temp = path.with_name(path.name + '.' + str(os.getpid()) + '.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    temp.replace(path)


def communication_status(base_file):
    root = Path(base_file).resolve().parent / 'runtime'
    result = {}
    for service in ('telegram','cloudflare'):
        try:
            data = json.loads((root/(service+'_status.json')).read_text(encoding='utf-8'))
            if time.time() - data['updated_at'] > 90 and data['state'] in {'connected','published','generated','publishing'}:
                data = {**data,'state':'stale','message':'Sem confirmacao recente de comunicacao.'}
            result[service] = data
        except (OSError,ValueError,KeyError):
            result[service] = dict(state='waiting',message='Aguardando inicializacao.',url='',bot='')
    return result


def start_communication_monitor(base_file):
    global _started
    with _guard:
        if _started:
            return
        _started = True
    def worker():
        previous = {}
        while True:
            for service,data in communication_status(base_file).items():
                key = (data['state'],data['message'],data.get('url'),data.get('bot'))
                if previous.get(service) != key:
                    stamp = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                    print(f"[{stamp}] [{service.upper()}] {data['message']}",flush=True)
                    if data.get('url'):
                        print(f"[{stamp}] [IMPRESSORAS] Link atual de comunicacao: {data['url']}",flush=True)
                    previous[service] = key
            time.sleep(2)
    threading.Thread(target=worker,name='communication-status',daemon=True).start()
