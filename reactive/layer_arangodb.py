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
import random
from base64 import b64encode
from charms import leadership
from charms.reactive import when, when_not, set_flag, is_flag_set
from charmhelpers.core import unitdata
from charmhelpers.core.templating import render
from charmhelpers.core.host import service_restart, service_stop
from charmhelpers.core.hookenv import status_set, open_port, close_port, config, unit_public_ip, leader_get, leader_set, unit_private_ip



kv = unitdata.kv()
################################################################################
# Install
################################################################################
@when('apt.installed.arangodb3', 'secrets.configured')
@when_not('arangodb.installed')
def configure_arangodb():
    status_set('maintenance', 'configuring ArangoDB')
    install_standalone()
    status_set('active', 'ArangoDB running with root password {}'.format(kv.get('password')))
    set_flag('arangodb.installed')

@when('arangodb.installed', 'db.available')
def configure_http(db):
    conf = config()
    db.configure(conf['port'], kv.get('username'), kv.get('password'))


@when('arangodb.installed', 'config.changed')
def change_configuration():
    status_set('maintenance', 'configuring ArangoDB')
    conf = config()
    change_config(conf)
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
    leader_set({'password': password, 'master_ip': unit_private_ip()})
    kv.set('password', password)
    set_flag('secrets.configured')


@when_not('leadership.is_leader', 'secrets.configured')
def set_secrets_local():
    kv.set('password', leader_get()['password'])
    status_set('active', 'ArangoDB running with root password {}'.format(kv.get('password')))
    set_flag('secrets.configured')
################################################################################
# clustering
################################################################################
@when('cluster.connected')
def configure_cluster(cluster):
    units = cluster.get_peer_addresses()
    install_cluster(units, True)

@when('cluster.depaterd')
def change_cluster(cluster):
    units = cluster.get_peer_addresses()
    install_cluster(units)
################################################################################
# Helper Functions
################################################################################
def change_config(conf):
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


def install_cluster(units, expanded=False):
    print(units, len(units))
    if len(units) == 0:
        service_restart('arangodb')
    elif expanded:
        if len(units) == 1:
            for unit in units:
                if unit_private_ip() != leader_get('master_ip'):
                    status_set('blocked', 'Arangodb needs at least three units to run in cluster mode!')
                    service_stop('arangodb')
        elif len(units) == 2:
            install_clustered(units)
        else:
            upgrade_cluster(units)
    else:
        if len(units) == 1:
            status_set('blocked', 'Arangodb needs at least three units to run in cluster mode!')
            subprocess.check_call(['arangodb', 'stop'])
        else:
            remove_cluster_node(units)


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


def install_clustered(units):
    service_stop('arangodb')
    if not is_flag_set('arangodb.clustered'):
        if unit_private_ip() == leader_get('master_ip'):
            subprocess.check_call(['arangodb', 'start'])
            status_set('active', '[MASTER] ArangoDB running in Cluster mode')
        else:
            #subprocess.check_call(['arangodb', 'start', '--starter.join', leader_get('master_ip')])
            subprocess.Popen(['arangodb', '--starter.join', leader_get('master_ip')])
            status_set('active', 'ArangoDB running in Cluster mode')
    set_flag('arangodb.clusterd')

def upgrade_cluster(units):
    if not unit_private_ip() in units:
        service_stop('arangodb')
        subprocess.Popen(['arangodb', '--starter.join', random.choice(units)])
        status_set('active', 'ArangoDB running in Cluster mode')

def remove_cluster_node(units):
    if not leader_get('master_ip') in units:
        leader_set({'master_ip': random.choice(units)})
