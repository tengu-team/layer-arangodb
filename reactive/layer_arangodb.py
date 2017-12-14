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
from charms.reactive import when, when_not, set_state
from charmhelpers.core import unitdata
from charmhelpers.core.templating import render
from charmhelpers.core.host import service_restart, service_stop
from charmhelpers.core.hookenv import status_set, open_port, close_port, config, unit_public_ip, leader_get, leader_set, unit_private_ip



kv = unitdata.kv()
################################################################################
# Install
################################################################################
@when('apt.installed.arangodb3')
@when_not('arangodb.installed')
def configure_arangodb():
    status_set('maintenance', 'configuring ArangoDB')
    install_standalone()
    status_set('active', 'ArangoDB running with root password {}'.format(kv.get('password')))
    set_state('arangodb.installed')

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
    password = leader_get().get('password', kv.get('password'))
    leader_set({'password': password , 'first_ip': unit_private_ip()})
    kv.set('password', password)
    set_state('secrets.configured')


@when('arangodb.installed')
@when_not('leadership.is_leader')
def set_secrets_local():
    kv.set('password', leader_get()['password'])
    status_set('active', 'ArangoDB running with root password {}'.format(kv.get('password')))
################################################################################
# clustering
################################################################################
@when('cluster.joined')
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
    kv.set('cluster', units)
    if len(units) == 1:
        install_standalone()
    elif expanded:
        if len(units) == 2:
            for unit in units:
                if unit == leader_get('first_ip'):
                    install_standalone()
                else:
                    status_set('blocked', 'Arangodb needs at least three units to run in clustering mode!')
        else:
            install_clustered(units)
    else:
        if len(units) == 2:
            status_set('blocked', 'Arangodb needs at least three units to run in clustering mode!')
            subprocess.check_call(['arangodb', 'stop'])
        else:
            upgrade_cluster(units)


def install_standalone():
    conf = config()
    password = conf['root_password']
    kv.set('username', 'root')
    render(source='arangod.conf',
           target='/etc/arangodb3/arangod.conf',
           context={
               'port': str(conf['port']),
               'authentication': str(conf['authentication']).lower()
           })
    if password == "" and not leader_get()['password']:
        password = b64encode(os.urandom(18)).decode('utf-8')
        require = "require('@arangodb/users').update('root', '{}', true)".format(password)
        subprocess.check_call(['arangosh', '--server.username', 'root', '--server.password', '', '--javascript.execute-string', require])
    else:
        password = leader_get()['password']
    kv.set('password', password)
    open_port(conf['port'])
    service_restart('arangodb')


def install_clustered(units):
    service_stop('arangodb')
    for unit in units:
        if unit == leader_get('master_ip'):
            subprocess.check_call(['arangodb', 'start'])
        else:
            subprocess.check_call(['arangodb', 'start', '--starter.join', leader_get('master_ip')])

def upgrade_cluster(units):
    rest = units.remove(unit_private_ip())
    subprocess.check_call(['arangodb', 'start', '--starter.join', random.choice(rest)])
