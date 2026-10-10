import json
from types import SimpleNamespace
import pytest
import requests
import ddns_updater as app
from providers.provider_ydns import YDNS
from providers.ddns_provider import ProviderError

IP = '192.0.2.1'
SETTINGS = {'hostname':'example.ydns.io','username':'user','password':'private-password'}

@pytest.fixture
def http(monkeypatch):
    calls = []
    monkeypatch.setattr(requests.sessions.Session, 'request', lambda *a, **k: pytest.fail('Real HTTP prohibited'))
    def get(url, **kwargs):
        calls.append((url,kwargs))
        return SimpleNamespace(status_code=200,text=IP if 'ipify' in url else 'good',close=lambda:None)
    monkeypatch.setattr(requests,'get',get)
    return calls

@pytest.mark.parametrize('record_id', ['1','1234','0001234','9'*20])
def test_specific_record_encoded_with_existing_host_auth(http, record_id):
    assert YDNS('test',dict(SETTINGS,record_id=record_id)).update_ddns() is True
    url, kwargs = http[-1]
    assert url == 'https://ydns.io/api/v1/update/'
    assert kwargs['params'] == {'host':SETTINGS['hostname'],'ip':IP,'record_id':record_id}
    assert kwargs['auth'] == ('user','private-password')

@pytest.mark.parametrize('value', ['', '0', '000', '-1', '+1', '1.5', '1&host=other', '１２', '1 '*2, '1'*21, 1234, None])
def test_invalid_direct_record_id_before_discovery(http, value):
    with pytest.raises(ProviderError):
        YDNS('test',dict(SETTINGS,record_id=value))
    assert not http

def test_omitted_record_id_preserves_request(http):
    assert YDNS('test',SETTINGS).update_ddns() is True
    assert http[-1][1]['params'] == {'host':SETTINGS['hostname'],'ip':IP}

def config(path, identifier):
    path.write_text('[one]\nddns_provider=YDNS\n'+''.join(f'{k}={v}\n' for k,v in SETTINGS.items())+'record_id='+identifier+'\n')

@pytest.mark.parametrize('value',['', '0','-1','SECRET','1'*21])
def test_invalid_cli_before_logs_state_or_network(http, tmp_path, monkeypatch, value, capsys):
    monkeypatch.chdir(tmp_path)
    path = tmp_path/'config.ini'
    config(path,value)
    args = ['--state-file',str(tmp_path/'state.json'),'--refresh-seconds','60']
    assert app.main(args) == 2
    assert app.main(['--dry-run']) == 2
    assert not http and not (tmp_path/'state.json').exists() and not (tmp_path/'ddns_update.log').exists()
    assert value != 'SECRET' or 'SECRET' not in capsys.readouterr().err

def test_record_selection_changes_acceptance_identity(http, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(app.time,'time',lambda:100)
    path = tmp_path/'config.ini'
    config(path,'1234')
    state = tmp_path/'state.json'
    args = ['--no-log','--state-file',str(state),'--refresh-seconds','60']
    assert app.main(args) == 0
    http.clear()
    assert app.main(args) == 0 and len(http) == 1
    config(path,'5678')
    http.clear()
    assert app.main(args) == 0 and len(http) == 2
    assert http[-1][1]['params']['record_id'] == '5678'
    assert len(json.loads(state.read_text())['entries']) == 2

def test_invalid_later_selection_blocks_all_services(http,tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path/'config.ini'
    config(path,'1234')
    path.write_text(path.read_text()+'[two]\nddns_provider=YDNS\nhostname=other.ydns.io\nusername=user\npassword=private\nrecord_id=bad\n')
    assert app.main(['--state-file',str(tmp_path/'state.json'),'--refresh-seconds','60']) == 2
    assert not http
