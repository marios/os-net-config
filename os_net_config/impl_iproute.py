# -*- coding: utf-8 -*-

# Copyright 2014 Red Hat, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import os_net_config
from os_net_config import objects
from os_net_config.openstack.common import processutils


class IPRouteNetConfig(os_net_config.NetConfig):
    """Configure network interfaces using iproute2."""

    def __init__(self):
        self.bridges = {}
        self.routes = {}
        self.interfaces = {}
        self.vlans = {}
        self.ip = 'ip'
        self.ovs_vsctl = 'ovs-vsctl'
        self.vconfig = 'vconfig'
        self.dhclient = 'dhclient'

    def _addCommon(self, interface, static_addr=None):
        cmd_data = ""
        address_cmd = ""
        if static_addr:
            #ip addr change
            address_cmd += "%s addr change %s/%s dev %s  ;  " % (
                self.ip, static_addr.ip, static_addr.netmask, interface.name)
        elif interface.use_dhcp:
            address_cmd += "%s -1 %s  ;  " % (self.dhclient, interface.name)
        if isinstance(interface, objects.OvsBridge):
            cmd_data = "%s add-br %s  ;  " % (self.ovs_vsctl, interface.name)
            cmd_data += address_cmd
            for port in interface.members:
                cmd_data += "%s add-port %s %s  ;  " % (
                    self.ovs_vsctl, port.bridge_name, port.name)
        elif interface.ovs_port:
            cmd_data = "%s link add name %s type veth  ;  " % (
                self.ip, interface.name)
            cmd_data += address_cmd
            cmd_data += "%s add-port %s %s  ;  " % (
                self.ovs_vsctl, interface.bridge_name, interface.name)
        elif isinstance(interface, objects.Vlan):
            # ip link add link eth0 name eth0.vlan1 type vlan id 1
            cmd_data = "%s link add link %s name %s type vlan id %s  ;  " % (
                self.ip, interface.device, interface.name, interface.vlan_id)
        elif isinstance(interface, objects.OvsBond):
            ifaces = ""
            for iface in interface.members:
                ifaces += "  %s  " % iface.name
            cmd_data = "%s add-bond %s %s %s  ;  " % (
                self.ovs_vsctl, interface.bridge_name, interface.name, ifaces)
        else:
            cmd_data = "%s link add name %s type veth  ;  " % (
                self.ip, interface.name)
            cmd_data += address_cmd
        return cmd_data

    def _addRoutes(self, iface_name, routes=[]):
        route_cmd = ""
        for route in routes:
            route_cmd += "%s route add %s via %s  ;  " % (
                self.ip, route.ip_netmask, route.next_hop)
        self.routes[iface_name] = route_cmd

    def addInterface(self, interface):
        #TODO(marios): add support for multiple addresses
        static_addr = ''
        if interface.addresses:
            static_addr = interface.addresses[0]
        cmds = self._addCommon(interface, static_addr)
        self.interfaces[interface.name] = cmds
        if interface.routes:
            self._addRoutes(interface.name, interface.routes)

    def addVlan(self, vlan):
        data = self._addCommon(vlan)
        self.vlans[vlan.name] = data
        if vlan.routes:
            self._addRoutes(vlan.name, vlan.routes)

    def addBridge(self, bridge):
        data = self._addCommon(bridge)
        self.bridges[bridge.name] = data
        if bridge.routes:
            self._addRoutes(bridge.name, bridge.routes)

    def addBond(self, bond):
        data = self._addCommon(bond)
        self.interfaces[bond.name] = data
        if bond.routes:
            self._addRoutes(bond.name, bond.routes)

    def apply(self, mock=False):
        self.mock_commands = ""

        def _execute_cmds(cmds):
            for cmd in cmds:
                if cmd.strip() == '':
                    continue
                else:
                    binary = cmd.strip().split(' ')[0]
                    params = cmd.split(binary)[1]
                    if mock:
                        self.mock_commands += "%s%s;  " % (binary, params)
                    else:
                        processutils.execute(binary, params,
                                             check_exit_code=False)

        def _get_rts(obj_name):
            rts = self.routes.get(obj_name)
            rt_cmd = []
            if rts:
                rt_cmd = rts.split(';')
            return rt_cmd

        for iface_name, iface_data in self.interfaces.iteritems():
            iface_cmds = iface_data.split(';')
            if "ovs-vsctl add-port" in iface_data:
                br = iface_data.split('ovs-vsctl add-port')[1].replace(
                    "%s  ;  " % (iface_name), "").strip()
                cmd = 'ovs-vsctl add-port %s %s  ;  ' % (br, iface_name)
                if self.bridges[br]:
                    if cmd in self.bridges[br]:
                        iface_data = iface_data.replace(cmd, '')
            iface_cmds = iface_data.split(';')
            _execute_cmds(iface_cmds + _get_rts(iface_name))

        for bridge_name, bridge_data in self.bridges.iteritems():
            bridge_cmds = bridge_data.split(';')
            _execute_cmds(bridge_cmds + _get_rts(bridge_name))

        for vlan_name, vlan_data in self.vlans.iteritems():
            _execute_cmds([vlan_data])

        if mock:
            return self.mock_commands
