import json
from types import SimpleNamespace
import pytest
import requests
import ddns_updater as app
from providers.provider_godaddy import GoDaddyDDNS
from providers.ddns_provider import ProviderError, ProviderStopError

IP = '192.0.2.1'
SETTINGS = {'api_version':'v3','pat':'private-pat','domain':'example.org','hostname':'@','record_id':'record_123'}
GOOD = {'recordId':'record_123','name':'@','type':'A','data':IP,'ttl':600}

@pytest.fixture
def http(monkeypatch):
    calls = []
    control = {'body':json.dumps(GOOD),'status':200}
    monkeypatch.setattr(requests.sessions.Session,'request',lambda *a, **k: pytest.fail('Real HTTP prohibited'))
    def get(url, **kwargs):
        calls.append(('GET',url,kwargs))
        return SimpleNamespace(status_code=200,text=IP,close=lambda:None)
    def put(url, **kwargs):
        calls.append(('PUT',url,kwargs))
        return SimpleNamespace(status_code=control['status'],text=control['body'],close=lambda:None)
    monkeypatch.setattr(requests,'get',get)
    monkeypatch.setattr(requests,'put',put)
    return calls,control

def test_v3_pat_single_record_payload_and_acceptance(http):
    calls,_ = http
    assert GoDaddyDDNS('test',SETTINGS).update_ddns() is True
    method,url,kwargs = calls[-1]
    assert method == 'PUT' and url == 'https://api.godaddy.com/v3/domains/zones/example.org/dns-records/record_123'
    assert kwargs['headers']['Authorization'] == 'Bearer private-pat'
    assert kwargs['json'] == {'name':'@','type':'A','data':IP,'ttl':600}
    assert not kwargs['allow_redirects']

@pytest.mark.parametrize('key,value',[('api_version','v4'),('pat','bad\npat'),('record_id','../other'),('domain','éxample.org'),('domain','example..org'),('hostname','..'),('ttl','599'),('ttl','86401'),('ttl','1e3')])
def test_invalid_v3_before_discovery(http,key,value):
    calls,_=http
    with pytest.raises(ProviderError):
        GoDaddyDDNS('test',dict(SETTINGS,**{key:value}))
    assert not calls

@pytest.mark.parametrize('body',['','{}','[]','SECRET',json.dumps(dict(GOOD,data='192.0.2.2')),json.dumps(dict(GOOD,type='AAAA')),json.dumps(dict(GOOD,recordId='other')),json.dumps(dict(GOOD,ttl=True)),json.dumps(GOOD)[:-1]+',"ttl":600}'])
def test_unconfirmed_v3_body_stops(http,body):
    _,control=http
    control['body']=body
    with pytest.raises(ProviderStopError):
        GoDaddyDDNS('test',SETTINGS).update_ddns()

@pytest.mark.parametrize('status',[204,301,400,401,403,404,409,422,429,500])
def test_v3_http_rejection_stops(http,status):
    _,control=http
    control['status']=status
    with pytest.raises(ProviderStopError):
        GoDaddyDDNS('test',SETTINGS).update_ddns()

def config(path,settings):
    path.write_text('[one]\nddns_provider=GoDaddyDDNS\n'+''.join(f'{k}={v}\n' for k,v in settings.items()))

def test_cli_v3_required_fields_and_cache(http,tmp_path,monkeypatch):
    calls,_=http
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(app.time,'time',lambda:100)
    path=tmp_path/'config.ini'
    config(path,SETTINGS)
    assert app.main(['--dry-run']) == 0 and not calls
    args=['--no-log','--state-file',str(tmp_path/'state.json'),'--refresh-seconds','60']
    assert app.main(args) == 0
    calls.clear()
    assert app.main(args) == 0 and len(calls)==1

@pytest.mark.parametrize('field',['pat','record_id','domain','hostname'])
def test_missing_v3_fields_before_network(http,tmp_path,monkeypatch,field):
    calls,_=http
    monkeypatch.chdir(tmp_path)
    config(tmp_path/'config.ini',{k:v for k,v in SETTINGS.items() if k!=field})
    assert app.main(['--dry-run']) == 2 and not calls

def test_v1_stop_cannot_be_bypassed_with_v3(http,tmp_path,monkeypatch):
    calls,control=http
    monkeypatch.chdir(tmp_path)
    path=tmp_path/'config.ini'
    config(path,{'api_key':'key','api_secret':'secret','domain':'example.org','hostname':'@'})
    control['status']=401
    args=['--no-log','--state-file',str(tmp_path/'state.json'),'--refresh-seconds','60']
    assert app.main(args)==1
    config(path,SETTINGS)
    calls.clear()
    assert app.main(args)==1 and not calls
