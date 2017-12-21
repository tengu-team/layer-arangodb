#!/usr/bin/python3
# Copyright (C) 2017  Qrama
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# pylint: disable=c0111,c0103,c0301,e0401
import os
import subprocess
import json
from base64 import b64encode
from pathlib import Path
import time
import requests
from charms import leadership
from charms.reactive import when, when_not, set_flag, is_flag_set
from charmhelpers.core import unitdata
from charmhelpers.core.templating import render
from charmhelpers.core.host import service_restart, service_stop, service_start
from charmhelpers.core.hookenv import status_set, open_port, close_port, config, unit_public_ip, leader_get, leader_set, unit_private_ip, local_unit

kv = unitdata.kv()
DATA_DIR = '/opt/arangodb/{}'.format(local_unit().replace('/', '_'))
################################################################################
# Install
################################################################################
@when('apt.installed.arangodb3', 'secrets.configured')
@when_not('arangodb.installed')
def configure_arangodb():
    status_set('maintenance', 'configuring ArangoDB')
    if not os.path.isdir(DATA_DIR):
        os.makedirs(DATA_DIR)
    install_standalone()
    kv.set('port', config()['port'])
    status_set('active', 'ArangoDB running with root password {}'.format(kv.get('password')))
    set_flag('arangodb.installed')

@when('arangodb.installed', 'db.available')
def configure_interface(db):
    db.configure(kv.get('port'), kv.get('username'), kv.get('password'))


@when('arangodb.installed', 'config.changed')
def change_configuration():
    status_set('maintenance', 'configuring ArangoDB')
    change_config()
    service_restart('arangodb')
    status_set('active', 'ArangoDB running with root password {}'.format(kv.get('password')))

################################################################################
# Leadership
################################################################################
@when('leadership.is_leader')
@when_not('secrets.configured')
def set_secrets():
    password = config()['root_password']
    if  password == '':
        password = b64encode(os.urandom(18)).decode('utf-8')
    leader_set({'password': password, 'master_ip': unit_private_ip(), 'master_started': False})
    kv.set('password', password)
    set_flag('secrets.configured')


@when_not('leadership.is_leader', 'secrets.configured')
def set_secrets_local():
    kv.set('password', leader_get()['password'])
    set_flag('secrets.configured')
################################################################################
# clustering
################################################################################
@when('cluster.connected')
def configure_cluster(cluster):
    units = cluster.get_peer_addresses()
    install_cluster(units)

################################################################################
# Helper Functions
################################################################################
def change_config():
    conf = config()
    if conf.changed('port') or conf.changed('authentication'):
        old_port = conf.previous('port')
        render(source='arangod.conf',
               target='/etc/arangodb3/arangod.conf',
               context={
                   'port': str(conf['port']),
                   'authentication': str(conf['authentication']).lower()
               })
        if old_port is not None:
            close_port(old_port)
        open_port(conf['port'])
    if conf['root_password'] != kv.get('password') and conf['root_password'] != "":
        password = conf['root_password']
        old_password = kv.get('password')
        kv.set('password', password)
        TCP = 'tcp://' + unit_public_ip() + ':' + str(conf['port'])
        require = "require('@arangodb/users').update('root', '{}', true)".format(password)
        subprocess.check_call(['arangosh', '--server.endpoint', TCP, '--server.username', 'root', '--server.password', old_password, '--javascript.execute-string', require])


def install_cluster(units):
    if len(units) < 2:
        if not kv.get('cluster'):
            if unit_private_ip() != leader_get('master_ip'):
                status_set('blocked', 'Arangodb needs at least three units to run in cluster mode!')
                service_stop('arangodb')
        else:
            status_set('blocked', 'Arangodb needs at least three units to run in cluster mode!')
            remove_cluster_node(units)
    else:
        install_clustered()
        status_set('active', 'ArangoDB running in Cluster mode')
        kv.set('cluster', True)

def install_standalone():
    conf = config()
    kv.set('username', 'root')
    render(source='arangod.conf',
           target='/etc/arangodb3/arangod.conf',
           context={
               'port': str(conf['port']),
               'authentication': str(conf['authentication']).lower()
           })
    require = "require('@arangodb/users').update('root', '{}', true)".format(kv.get('password'))
    subprocess.check_call(['arangosh', '--server.username', 'root', '--server.password', '', '--javascript.execute-string', require])
    open_port(conf['port'])
    service_restart('arangodb')
    kv.set('cluster', False)
    status_set('active', 'ArangoDB running with root password {}'.format(kv.get('password')))


def install_clustered():
    service_stop('arangodb')
    if not is_flag_set('arangodb.clustered'):
        if unit_private_ip() == leader_get('master_ip'):
            render(source='arangodbcluster.service',
                   target='/etc/systemd/system/arangodbcluster.service',
                   context={'option': '--starter.data-dir={}'.format(DATA_DIR)})
            subprocess.check_call(['systemctl', 'daemon-reload'])
            subprocess.check_call(['systemctl', 'enable', 'arangodbcluster.service'])
            service_start('arangodbcluster')
            set_flag('arangodb.clustered')
            leader_set({'master_started': True})
        elif leader_get('master_started'):
            render(source='arangodbcluster.service',
                   target='/etc/systemd/system/arangodbcluster.service',
                   context={'option': '--starter.data-dir={} --starter.join {}'.format(DATA_DIR, leader_get('master_ip'))})
            subprocess.check_call(['systemctl', 'daemon-reload'])
            subprocess.check_call(['systemctl', 'enable', 'arangodbcluster.service'])
            service_start('arangodbcluster')
            #let the charm sleep for 15 seconds so that the setup file is created
            time.sleep(15)
            set_flag('arangodb.clustered')
    setup_file = Path('{}/setup.json'.format(DATA_DIR))
    if setup_file.exists():
        close_port(kv.get('port'))
        open_coordinater_port()


def remove_cluster_node(units):
    if not leader_get('master_ip') in units and is_flag_set('leadership.is_leader'):
        leader_set({'master_ip': '{}:{}'.format(unit_private_ip(), retrieve_helper_port())})

def retrieve_helper_port():
    with open('{}/setup.json'.format(DATA_DIR)) as json_file:
        json_data = json.load(json_file)
        for peer in json_data['peers']['Peers']:
            if peer['DataDir'] == DATA_DIR:
                return peer['Port'] + peer['PortOffset']

def open_coordinater_port():
    helper_port = retrieve_helper_port()
    res = requests.get('http://127.0.0.1:{}/process'.format(helper_port))
    for ip_adr in res.json()['servers']:
        if ip_adr['ip'] == unit_private_ip() and ip_adr['type'] == 'coordinator':
            open_port(ip_adr['port'])
