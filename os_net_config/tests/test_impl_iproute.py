# -*- coding: utf-8 -*-

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

import tempfile

from os_net_config import impl_iproute
from os_net_config import objects
from os_net_config.openstack.common import processutils
from os_net_config.tests import base

IP = 'ip'
OVS_VSCTL = 'ovs-vsctl'
DHCLIENT = 'dhclient'


def dhcp_string(iface="eth0"):
    return (DHCLIENT + " -1 %s  ;  " % (iface))


_V4_IFACE = IP + " link add name eth0 type veth  ;  "

_V4_IFACE_DHCP = _V4_IFACE + dhcp_string()

_V4_IFACE_STATIC_IP = (_V4_IFACE + IP + " addr change " +
                       "192.168.1.2/255.255.255.0 dev eth0  ;  ")

_V6_IFACE_STATIC_IP = (_V4_IFACE + IP + " addr change " +
                       "fe80::2677:3ff:fe7d:4c/ffff:ffff:ffff:ffff:ffff:" +
                       "ffff:ffff:ffff dev eth0  ;  ")

_OVS_PORT_IFACE = _V4_IFACE + OVS_VSCTL + " add-port br0 eth0  ;  "


_OVS_BRIDGE_PORT = (OVS_VSCTL + " add-br br0  ;  " + dhcp_string(iface="br0") +
                    OVS_VSCTL + " add-port br0 eth0  ;  ")

_OVS_BRIDGE_WITH_IFACE = _V4_IFACE + _OVS_BRIDGE_PORT

_VLAN = IP + " link add link eth0 name vlan5 type vlan id 5  ;  "

_VLAN_OVS_PORT = (OVS_VSCTL + " add-br br0  ;  " + dhcp_string(iface="br0") +
                  OVS_VSCTL + " add-port br0 vlan5  ;  ")

_RTS = IP + " route add 172.19.0.0/24 via 192.168.1.1  ;  "


class TestIPRouteNetConfig(base.TestCase):

    def setUp(self):
        super(TestIPRouteNetConfig, self).setUp()

        self.provider = impl_iproute.IPRouteNetConfig()
        self.if_name = 'eth0'

    def tearDown(self):
        super(TestIPRouteNetConfig, self).tearDown()

    def get_interface_config(self, name="eth0"):
        return self.provider.interfaces[name]

    def get_route_config(self):
        return self.provider.routes[self.if_name]

    def _default_interface(self, addr=[], rts=[]):
        return objects.Interface(self.if_name, addresses=addr, routes=rts)

    def test_interface_no_ip(self):
        interface = self._default_interface()
        self.provider.addInterface(interface)
        self.assertEqual(_V4_IFACE, self.get_interface_config())

    def test_add_interface_with_v4(self):
        v4_addr = objects.Address('192.168.1.2/24')
        interface = self._default_interface([v4_addr])
        self.provider.addInterface(interface)
        self.assertEqual(_V4_IFACE_STATIC_IP, self.get_interface_config())

    def test_add_interface_with_v6(self):
        v6_addr = objects.Address('fe80::2677:3ff:fe7d:4c')
        interface = self._default_interface([v6_addr])
        self.provider.addInterface(interface)
        self.assertEqual(_V6_IFACE_STATIC_IP, self.get_interface_config())

    def test_add_interface_dhcp(self):
        interface = self._default_interface()
        interface.use_dhcp = True
        self.provider.addInterface(interface)
        self.assertEqual(_V4_IFACE_DHCP, self.get_interface_config())

    def test_add_interface_with_both_v4_and_v6(self):
        pass
        """ Don't yet support multiple static addresses
        v4_addr = objects.Address('192.168.1.2/24')
        v6_addr = objects.Address('fe80::2677:3ff:fe7d:4c')
        interface = self._default_interface([v4_addr, v6_addr])
        self.provider.addInterface(interface)
        self.assertEqual(_V4_IFACE_STATIC_IP + _V6_IFACE_STATIC_IP,
                         self.get_interface_config())
        """

    def test_add_ovs_port_interface(self):
        interface = self._default_interface()
        interface.ovs_port = True
        interface.bridge_name = 'br0'
        self.provider.addInterface(interface)
        self.assertEqual(_OVS_PORT_IFACE, self.get_interface_config())

    def test_network_with_routes(self):
        route1 = objects.Route('192.168.1.1', '172.19.0.0/24')
        v4_addr = objects.Address('192.168.1.2/24')
        interface = self._default_interface([v4_addr], [route1])
        self.provider.addInterface(interface)
        self.assertEqual(_V4_IFACE_STATIC_IP, self.get_interface_config())
        self.assertEqual(_RTS, self.get_route_config())

    def test_network_ovs_bridge_with_port(self):
        interface = self._default_interface()
        bridge = objects.OvsBridge('br0', use_dhcp=True,
                                   members=[interface])
        self.provider.addBridge(bridge)
        self.provider.addInterface(interface)
        self.assertEqual(_OVS_PORT_IFACE, self.get_interface_config())
        self.assertEqual(_OVS_BRIDGE_PORT, self.provider.bridges['br0'])

    def test_vlan(self):
        vlan = objects.Vlan('eth0', 5)
        self.provider.addVlan(vlan)
        self.assertEqual(_VLAN, self.provider.vlans['vlan5'])

    def test_vlan_ovs_bridge_int_port(self):
        vlan = objects.Vlan('eth0', 5)
        bridge = objects.OvsBridge('br0', use_dhcp=True,
                                   members=[vlan])
        self.provider.addBridge(bridge)
        self.provider.addVlan(vlan)
        self.assertEqual(_VLAN_OVS_PORT, self.provider.bridges['br0'])


class TestIPRouteNetConfigApply(base.TestCase):

    def setUp(self):
        super(TestIPRouteNetConfigApply, self).setUp()
        self.temp_config_file = tempfile.NamedTemporaryFile()

        def test_execute(*args, **kwargs):
            pass
        self.stubs.Set(processutils, 'execute', test_execute)

        self.provider = impl_iproute.IPRouteNetConfig()

    def tearDown(self):
        super(TestIPRouteNetConfigApply, self).tearDown()

    def test_network_apply(self):
        route = objects.Route('192.168.1.1', '172.19.0.0/24')
        v4_addr = objects.Address('192.168.1.2/24')
        interface = objects.Interface('eth0', addresses=[v4_addr],
                                      routes=[route])
        self.provider.addInterface(interface)
        cmds = self.provider.apply(mock=True)
        self.assertEqual((_V4_IFACE_STATIC_IP + _RTS), cmds)

    def test_ovs_bridge_interface_apply(self):
        interface = objects.Interface('eth0')
        bridge = objects.OvsBridge('br0', use_dhcp=True,
                                   members=[interface])
        self.provider.addInterface(interface)
        self.provider.addBridge(bridge)
        cmds = self.provider.apply(mock=True)
        self.assertEqual((_OVS_BRIDGE_WITH_IFACE), cmds)
