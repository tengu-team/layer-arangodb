mport os
import subprocess
from base64 import b64encode
from charmhelpers.core import unitdata
from charmhelpers.core.templating import render
from charmhelpers.core.host import service_restart
from charms.reactive import when, when_not, set_state
from charmhelpers.core.hookenv import status_set, open_port, close_port, config

kv = unitdata.kv()

@when('apt.installed.arangodb3')
@when_not('arangodb.configured')
def configure_arangodb():
    status_set('maintenance', 'configuring ArangoDB')
    conf = config()
    port = conf['port']
    authn = conf['authentication']
    password =conf['root_password']
    if password == "root" or "":
        password = b64encode(os.urandom(18)).decode('utf-8')
    kv.set('password', password)
    render(source='arangod.conf',
           target='/etc/arangodb3/arangod.conf',
           context={
               'port': str(port),
               'authentication': str(authn).lower()
           })
    require = 'require("@arangodb/users").update("root", "{}", true)'.format(password)
    subprocess.check_call(['arangosh', '--server.username', 'root', '--server.password', '', '--javascript.execute-string', require])
    open_port(port)
    set_state('arangodb.configured')

@when('arangodb.configured')
@when_not('arangodb.running')
def start_arangodb():
    service_restart("arangodb3")
    status_set('active', 'ArangoDB running with admin password {}'.format(kv.get('password')))
    set_state('arangodb.running')

@when('arangodb.running', 'http.available')
def configure_http(http):
    conf = config()
    http.configure(conf['port'])

@when('arangodb.running', 'config.changed')
def change_configuration():
    status_set('maintenance', 'configuring ArangoDB')
    conf = config()
    port = conf['port']
    old_port = conf.previous('port')
    authn = conf['authentication']
    if conf.changed('port') or conf.changed('authentication'):
        render(source='arangod.conf',
               target='/etc/arangodb3/arangod.conf',
               context={
                   'port': str(port),
                   'authentication': str(authn).lower()
               })
        if old_port is not None:
           close_port(old_port)
        open_port(port)
    if conf['root_password'] != kv.get('password') and conf['root_password'] != "root":
        password = conf['root_password']
        old_password = kv.get('password')
        kv.set('password', password)
        require = 'require("@arangodb/users").update("root", "{}", true)'.format(password)
        subprocess.check_call(['arangosh', '--server.username', 'root', '--server.password', old_password, '--javascript.execute-string', require])
    service_restart("arangodb3")
    status_set('active', 'ArangoDB running with admin password {}'.format(kv.get('password')))
