import subprocess
from charms.reactive import when, when_not, set_state
from charmhelpers.core.hookenv import status_set, open_port, close_port, config
from charmhelpers.core.host import service_restart
from charmhelpers.core.templating import render

@when('apt.installed.arangodb3')
@when_not('arangodb.configured')
def configure_arangodb():
    status_set('maintenance', 'configuring ArangoDB')
    conf = config()
    port = conf['port']
    authn = conf['authentication']
    render(source='arangod.conf',
           target='/etc/arangodb3/arangod.conf',
           context={
               'port': str(port),
               'authentication': str(authn).lower()
           })
    open_port(port)
    set_state('arangodb.configured')

@when('arangodb.configured')
@when_not('arangodb.running')
def start_arangodb():
    service_restart("arangodb3")
    status_set('active', '(Ready) ArangoDB started')
    set_state('arangodb.running')

@when('arangodb.running', 'http.available')
@when_not('arangodb.http-configured')
def configure_http(http):
    status_set('maintenance', 'configuring http')
    conf = config()
    http.configure(conf['port'])
    set_state('arangodb.http-configured')

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
        service_restart("arangodb3")
    status_set('active', '(Ready) Arangodb started')
    
