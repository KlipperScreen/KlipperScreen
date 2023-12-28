# python-networkmanager - Easy communication with NetworkManager
# Copyright (C) 2011-2021 Dennis Kaarsemaker <dennis@kaarsemaker.net>
#
# This software is provided 'as-is', without any express or implied
# warranty. In no event will the authors be held liable for any damages
# arising from the use of this software.
#
# Permission is granted to anyone to use this software for any purpose,
# including commercial applications, and to alter it and redistribute it
# freely, subject to the following restrictions:
#
# 1. The origin of this software must not be misrepresented; you must not
#    claim that you wrote the original software. If you use this software
#    in a product, an acknowledgement in the product documentation would be
#    appreciated but is not required.
# 2. Altered source versions must be plainly marked as such, and must not be
#    misrepresented as being the original software.
# 3. This notice may not be removed or altered from any source distribution.
# NetworkManager - a library to make interacting with the NetworkManager daemon
# easier.
#
# (C)2011-2021 Dennis Kaarsemaker
# License: zlib

import contextlib
import copy
import dbus
import dbus.service
import six
import socket
import struct
import time
import warnings
import xml.etree.ElementTree as ET


class ObjectVanished(Exception):
    def __init__(self, obj):
        self.obj = obj
        super(ObjectVanished, self).__init__(obj.object_path)


class SignalDispatcher(object):
    def __init__(self):
        self.handlers = {}
        self.args = {}
        self.interfaces = set()
        self.setup = False

    def setup_signals(self):
        if not self.setup:
            bus = dbus.SystemBus()
            for interface in self.interfaces:
                bus.add_signal_receiver(self.handle_signal, dbus_interface=interface, interface_keyword='interface',
                                        member_keyword='signal', path_keyword='path')
            self.setup = True
        self.listen_for_restarts()

    def listen_for_restarts(self):
        # If we have a mainloop, listen for disconnections
        if not NMDbusInterface.last_disconnect and dbus.get_default_main_loop():
            dbus.SystemBus().add_signal_receiver(self.handle_restart, 'NameOwnerChanged', 'org.freedesktop.DBus')
            NMDbusInterface.last_disconnect = 1

    def add_signal_receiver(self, interface, signal, obj, func, args, kwargs):
        self.setup_signals()
        key = (interface, signal)
        if key not in self.handlers:
            self.handlers[key] = []
        self.handlers[key].append((obj, func, args, kwargs))

    def handle_signal(self, *args, **kwargs):
        key = (kwargs['interface'], kwargs['signal'])
        skwargs = {}
        sargs = []
        if key not in self.handlers:
            return
        try:
            sender = fixups.base_to_python(kwargs['path'])
            for arg, (name, signature) in zip(args, self.args[key]):
                if name:
                    skwargs[name] = fixups.to_python(type(sender).__name__, kwargs['signal'], name, arg, signature)
                else:
                    # Older NetworkManager versions don't supply attribute names. Hope for the best.
                    sargs.append(fixups.to_python(type(sender).__name__, kwargs['signal'], None, arg, signature))
        except dbus.exceptions.DBusException:
            # This happens if the sender went away. Tough luck, no signal for you.
            return
        to_delete = []
        for pos, (match, receiver, rargs, rkwargs) in enumerate(self.handlers[key]):
            try:
                match == sender
            except ObjectVanished:
                to_delete.append(pos)
                continue
            if match == sender:
                rkwargs['interface'] = kwargs['interface']
                rkwargs['signal'] = kwargs['signal']
                rkwargs.update(skwargs)
                receiver(sender, *(sargs + rargs), **rkwargs)
        for pos in reversed(to_delete):
            self.handlers[key].pop(pos)

    def handle_restart(self, name, old, new):
        if not str(new) or str(name) != 'org.freedesktop.NetworkManager':
            return
        NMDbusInterface.last_disconnect = time.time()
        time.sleep(1)  # Give NetworkManager a bit of time to start and rediscover itself.
        for key in self.handlers:
            val, self.handlers[key] = self.handlers[key], []
            for obj, func, args, kwargs in val:
                with contextlib.suppress(ObjectVanished):
                    # This resets the object path if needed
                    obj.proxy
                    self.add_signal_receiver(key[0], key[1], obj, func, args, kwargs)


SignalDispatcher = SignalDispatcher()

# We completely dynamically generate all classes using introspection data. As
# this is done at import time, use a special dbus connection that does not get
# in the way of setting a mainloop and doing async stuff later.
init_bus = dbus.SystemBus(private=True)
xml_cache = {}


class NMDbusInterfaceType(type):
    """Metaclass that generates our classes based on introspection data"""
    dbus_service = 'org.freedesktop.NetworkManager'

    def __new__(cls, name, bases, attrs):
        attrs['dbus_service'] = cls.dbus_service
        attrs['properties'] = []
        attrs['introspection_data'] = None
        attrs['signals'] = []

        # Derive the interface name from the name of the class, but let classes
        # override it if needed
        if 'interface_names' not in attrs and 'NMDbusInterface' not in name:
            attrs['interface_names'] = [f'org.freedesktop.NetworkManager.{name}']
            for base in bases:
                if hasattr(base, 'interface_names'):
                    attrs['interface_names'] = [
                        f'{base.interface_names[0]}.{name}'
                    ] + base.interface_names
                    break
        else:
            for base in bases:
                if hasattr(base, 'interface_names'):
                    attrs['interface_names'] += base.interface_names
                    break

        if 'interface_names' in attrs:
            SignalDispatcher.interfaces.update(attrs['interface_names'])

        # If we know where to find this object, let's introspect it and
        # generate properties and methods
        if 'object_path' in attrs and attrs['object_path']:
            proxy = init_bus.get_object(cls.dbus_service, attrs['object_path'])
            attrs['introspection_data'] = proxy.Introspect(dbus_interface='org.freedesktop.DBus.Introspectable')
            root = ET.fromstring(attrs['introspection_data'])
            for element in root:
                if element.tag == 'interface' and element.attrib['name'] in attrs['interface_names']:
                    for item in element:
                        if item.tag == 'property':
                            attrs[item.attrib['name']] = cls.make_property(
                                name, element.attrib['name'], item.attrib
                            )
                            attrs['properties'].append(item.attrib['name'])
                        elif item.tag == 'method':
                            aname = item.attrib['name']
                            if aname in attrs:
                                aname = f'_{aname}'
                            attrs[aname] = cls.make_method(
                                name,
                                element.attrib['name'],
                                item.attrib,
                                list(item),
                            )
                        elif item.tag == 'signal':
                            SignalDispatcher.args[(element.attrib['name'], item.attrib['name'])] = [
                                (arg.attrib.get('name', None), arg.attrib['type']) for arg in item]
                            attrs['On' + item.attrib['name']] = cls.make_signal(
                                name, element.attrib['name'], item.attrib
                            )
                            attrs['signals'].append(item.attrib['name'])

        return super(NMDbusInterfaceType, cls).__new__(cls, name, bases, attrs)

    @staticmethod
    def make_property(cls, interface, attrib):
        name = attrib['name']

        def get_func(self):
            try:
                data = self.proxy.Get(interface, name, dbus_interface='org.freedesktop.DBus.Properties')
            except dbus.exceptions.DBusException as e:
                if e.get_dbus_name() == 'org.freedesktop.DBus.Error.UnknownMethod':
                    raise ObjectVanished(self)
                raise
            return fixups.to_python(cls, 'Get', name, data, attrib['type'])

        if attrib['access'] == 'read':
            return property(get_func)

        def set_func(self, value):
            value = fixups.to_dbus(cls, 'Set', name, value, attrib['type'])
            try:
                return self.proxy.Set(interface, name, value, dbus_interface='org.freedesktop.DBus.Properties')
            except dbus.exceptions.DBusException as e:
                if e.get_dbus_name() == 'org.freedesktop.DBus.Error.UnknownMethod':
                    raise ObjectVanished(self)
                raise

        return property(get_func, set_func)

    @staticmethod
    def make_method(cls, interface, attrib, args):
        name = attrib['name']
        outargs = [x for x in args if x.tag == 'arg' and x.attrib['direction'] == 'out']
        outargstr = ', '.join([x.attrib['name'] for x in outargs]) or 'ret'
        args = [x for x in args if x.tag == 'arg' and x.attrib['direction'] == 'in']
        argstr = ', '.join([x.attrib['name'] for x in args])
        ret = {}
        code = "def %s(self%s):\n" % (name, f', {argstr}' if argstr else '')
        for arg in args:
            argname = arg.attrib['name']
            signature = arg.attrib['type']
            code += "    %s = fixups.to_dbus('%s', '%s', '%s', %s, '%s')\n" % (
                argname, cls, name, argname, argname, signature)
        code += "    try:\n"
        code += "        %s = dbus.Interface(self.proxy, '%s').%s(%s)\n" % (outargstr, interface, name, argstr)
        code += "    except dbus.exceptions.DBusException as e:\n"
        code += "        if e.get_dbus_name() == 'org.freedesktop.DBus.Error.UnknownMethod':\n"
        code += "            raise ObjectVanished(self)\n"
        code += "        raise\n"
        for arg in outargs:
            argname = arg.attrib['name']
            signature = arg.attrib['type']
            code += "    %s = fixups.to_python('%s', '%s', '%s', %s, '%s')\n" % (
                argname, cls, name, argname, argname, signature)
        code += f"    return ({outargstr})"
        exec(code, globals(), ret)
        return ret[name]

    @staticmethod
    def make_signal(cls, interface, attrib):
        name = attrib['name']
        ret = {}
        code = f"def On{name}(self, func, *args, **kwargs):"
        code += f"    SignalDispatcher.add_signal_receiver('{interface}', '{name}', self, func, list(args), kwargs)"
        exec(code, globals(), ret)
        return ret[f'On{name}']


@six.add_metaclass(NMDbusInterfaceType)
class NMDbusInterface(object):
    object_path = None
    last_disconnect = 0
    is_transient = False

    def __new__(cls, object_path=None):
        # If we didn't introspect this one at definition time, let's do it now.
        if object_path and not cls.introspection_data:
            proxy = dbus.SystemBus().get_object(cls.dbus_service, object_path)
            cls.introspection_data = proxy.Introspect(dbus_interface='org.freedesktop.DBus.Introspectable')
            root = ET.fromstring(cls.introspection_data)
            for element in root:
                if element.tag == 'interface' and element.attrib['name'] in cls.interface_names:
                    for item in element:
                        if item.tag == 'property':
                            setattr(cls, item.attrib['name'],
                                    type(cls).make_property(cls.__name__, element.attrib['name'], item.attrib))
                            cls.properties.append(item.attrib['name'])
                        elif item.tag == 'method':
                            aname = item.attrib['name']
                            if hasattr(cls, aname):
                                aname = f'_{aname}'
                            setattr(cls, aname,
                                    type(cls).make_method(cls.__name__, element.attrib['name'], item.attrib,
                                                          list(item)))
                        elif item.tag == 'signal':
                            SignalDispatcher.args[(element.attrib['name'], item.attrib['name'])] = [
                                (arg.attrib.get('name', None), arg.attrib['type']) for arg in item]
                            setattr(cls, 'On' + item.attrib['name'],
                                    type(cls).make_signal(cls.__name__, element.attrib['name'], item.attrib))
                            cls.signals.append(item.attrib['name'])

        SignalDispatcher.listen_for_restarts()
        return super(NMDbusInterface, cls).__new__(cls)

    def __init__(self, object_path=None):
        if isinstance(object_path, NMDbusInterface):
            object_path = object_path.object_path
        self.object_path = self.object_path or object_path
        self._proxy = None

    def __eq__(self, other):
        return isinstance(other, NMDbusInterface) and self.object_path and other.object_path == self.object_path

    @property
    def proxy(self):
        if not self._proxy:
            self._proxy = dbus.SystemBus().get_object(self.dbus_service, self.object_path,
                                                      follow_name_owner_changes=True)
            self._proxy.created = time.time()
        elif self._proxy.created < self.last_disconnect:
            if self.is_transient:
                raise ObjectVanished(self)
            obj = type(self)(self.object_path)
            if obj.object_path != self.object_path:
                self.object_path = obj.object_path
            self._proxy = dbus.SystemBus().get_object(self.dbus_service, self.object_path)
            self._proxy.created = time.time()
        return self._proxy

    # Backwards compatibility interface
    def connect_to_signal(self, signal, handler, *args, **kwargs):
        return getattr(self, f'On{signal}')(handler, *args, **kwargs)


class TransientNMDbusInterface(NMDbusInterface):
    is_transient = True


class NetworkManager(NMDbusInterface):
    interface_names = ['org.freedesktop.NetworkManager']
    object_path = '/org/freedesktop/NetworkManager'

    # noop method for backward compatibility. It is no longer necessary to call
    # this but let's not break code that does so.
    def auto_reconnect(self):
        pass


class Statistics(NMDbusInterface):
    object_path = '/org/freedesktop/NetworkManager/Statistics'


class Settings(NMDbusInterface):
    object_path = '/org/freedesktop/NetworkManager/Settings'


class AgentManager(NMDbusInterface):
    object_path = '/org/freedesktop/NetworkManager/AgentManager'


class Connection(NMDbusInterface):
    interface_names = ['org.freedesktop.NetworkManager.Settings.Connection']
    has_secrets = ['802-1x', '802-11-wireless-security', 'cdma', 'gsm', 'pppoe', 'vpn']

    def __init__(self, object_path):
        super(Connection, self).__init__(object_path)
        self.uuid = self.GetSettings()['connection']['uuid']

    def GetSecrets(self, name=None):
        settings = self.GetSettings()
        if name is None:
            name = settings['connection']['type']
            name = settings[name].get('security', name)
        try:
            return self._GetSecrets(name)
        except dbus.exceptions.DBusException as e:
            if e.get_dbus_name() != 'org.freedesktop.NetworkManager.AgentManager.NoSecrets':
                raise
            return {key: {} for key in settings}

    @staticmethod
    def all():
        return Settings.ListConnections()

    def __eq__(self, other):
        return isinstance(other, type(self)) and self.uuid == other.uuid


class ActiveConnection(TransientNMDbusInterface):
    interface_names = ['org.freedesktop.NetworkManager.Connection.Active']

    def __new__(cls, object_path):
        if cls == ActiveConnection:
            # Automatically turn this into a VPNConnection if needed
            obj = dbus.SystemBus().get_object(cls.dbus_service, object_path)
            if obj.Get('org.freedesktop.NetworkManager.Connection.Active', 'Vpn',
                       dbus_interface='org.freedesktop.DBus.Properties'):
                return VPNConnection.__new__(VPNConnection, object_path)
        return super(ActiveConnection, cls).__new__(cls, object_path)

    def __eq__(self, other):
        return isinstance(other, type(self)) and self.Uuid == other.Uuid


class VPNConnection(ActiveConnection):
    interface_names = ['org.freedesktop.NetworkManager.VPN.Connection']


class Device(NMDbusInterface):
    interface_names = ['org.freedesktop.NetworkManager.Device', 'org.freedesktop.NetworkManager.Device.Statistics']

    def __new__(cls, object_path):
        if cls == Device:
            # Automatically specialize the device
            with contextlib.suppress(ObjectVanished):
                obj = dbus.SystemBus().get_object(cls.dbus_service, object_path)
                cls = device_class(obj.Get('org.freedesktop.NetworkManager.Device', 'DeviceType',
                                           dbus_interface='org.freedesktop.DBus.Properties'))
                return cls.__new__(cls, object_path)
        return super(Device, cls).__new__(cls, object_path)

    @staticmethod
    def all():
        return NetworkManager.Devices

    def __eq__(self, other):
        return isinstance(other, type(self)) and self.IpInterface == other.IpInterface

    # Backwards compatibility method. Devices now auto-specialize, so this is
    # no longer needed. But code may use it.
    def SpecificDevice(self):
        return self


def device_class(typ):
    return {
        NM_DEVICE_TYPE_ADSL: Adsl,
        NM_DEVICE_TYPE_BOND: Bond,
        NM_DEVICE_TYPE_BRIDGE: Bridge,
        NM_DEVICE_TYPE_BT: Bluetooth,
        NM_DEVICE_TYPE_ETHERNET: Wired,
        NM_DEVICE_TYPE_GENERIC: Generic,
        NM_DEVICE_TYPE_INFINIBAND: Infiniband,
        NM_DEVICE_TYPE_IP_TUNNEL: IPTunnel,
        NM_DEVICE_TYPE_MACVLAN: Macvlan,
        NM_DEVICE_TYPE_MODEM: Modem,
        NM_DEVICE_TYPE_OLPC_MESH: OlpcMesh,
        NM_DEVICE_TYPE_TEAM: Team,
        NM_DEVICE_TYPE_TUN: Tun,
        NM_DEVICE_TYPE_VETH: Veth,
        NM_DEVICE_TYPE_VLAN: Vlan,
        NM_DEVICE_TYPE_VXLAN: Vxlan,
        NM_DEVICE_TYPE_WIFI: Wireless,
        NM_DEVICE_TYPE_WIMAX: Wimax,
        NM_DEVICE_TYPE_MACSEC: MacSec,
        NM_DEVICE_TYPE_DUMMY: Dummy,
        NM_DEVICE_TYPE_PPP: PPP,
        NM_DEVICE_TYPE_OVS_INTERFACE: OvsIf,
        NM_DEVICE_TYPE_OVS_PORT: OvsPort,
        NM_DEVICE_TYPE_OVS_BRIDGE: OvsBridge,
        NM_DEVICE_TYPE_WPAN: Wpan,
        NM_DEVICE_TYPE_6LOWPAN: SixLoWpan,
        NM_DEVICE_TYPE_WIREGUARD: WireGuard,
        NM_DEVICE_TYPE_VRF: Vrf,
        NM_DEVICE_TYPE_WIFI_P2P: WifiP2p,
    }[typ]


class Adsl(Device):
    pass


class Bluetooth(Device):
    pass


class Bond(Device):
    pass


class Bridge(Device):
    pass


class Generic(Device):
    pass


class Infiniband(Device):
    pass


class IPTunnel(Device):
    pass


class Macvlan(Device):
    pass


class Modem(Device):
    pass


class OlpcMesh(Device):
    pass


class Team(Device):
    pass


class Tun(Device):
    pass


class Veth(Device):
    pass


class Vlan(Device):
    pass


class Vxlan(Device):
    pass


class Wimax(Device):
    pass


class Wired(Device):
    pass


class Wireless(Device):
    pass


class MacSec(Device):
    pass


class Dummy(Device):
    pass


class PPP(Device):
    pass


class OvsIf(Device):
    pass


class OvsPort(Device):
    pass


class OvsBridge(Device):
    pass


class Wpan(Device):
    pass


class SixLoWpan(Device):
    pass


class WireGuard(Device):
    pass


class WifiP2p(Device):
    pass


class Vrf(Device):
    pass


class NSP(TransientNMDbusInterface):
    interface_names = ['org.freedesktop.NetworkManager.Wimax.NSP']


class AccessPoint(NMDbusInterface):
    @staticmethod
    def all():
        for device in Device.all():
            if isinstance(device, Wireless):
                yield from device.AccessPoints

    def __eq__(self, other):
        return isinstance(other, type(self)) and self.HwAddress == other.HwAddress


class IP4Config(TransientNMDbusInterface):
    pass


class IP6Config(TransientNMDbusInterface):
    pass


class DHCP4Config(TransientNMDbusInterface):
    pass


class DHCP6Config(TransientNMDbusInterface):
    pass


# Evil hack to work around not being able to specify a method name in the
# dbus.service.method decorator.
class SecretAgentType(type(dbus.service.Object)):
    def __new__(cls, name, bases, attrs):
        if bases != (dbus.service.Object,):
            attrs['GetSecretsImpl'] = attrs.pop('GetSecrets')
        return super(SecretAgentType, cls).__new__(cls, name, bases, attrs)


@six.add_metaclass(SecretAgentType)
class SecretAgent(dbus.service.Object):
    object_path = '/org/freedesktop/NetworkManager/SecretAgent'
    interface_name = 'org.freedesktop.NetworkManager.SecretAgent'

    def __init__(self, identifier):
        self.identifier = identifier
        dbus.service.Object.__init__(self, dbus.SystemBus(), self.object_path)
        AgentManager.Register(self.identifier)

    @dbus.service.method(dbus_interface=interface_name, in_signature='a{sa{sv}}osasu', out_signature='a{sa{sv}}')
    def GetSecrets(self, connection, connection_path, setting_name, hints, flags):
        settings = fixups.to_python('SecretAgent', 'GetSecrets', 'connection', connection, 'a{sa{sv}}')
        connection = fixups.to_python('SecretAgent', 'GetSecrets', 'connection_path', connection_path, 'o')
        setting_name = fixups.to_python('SecretAgent', 'GetSecrets', 'setting_name', setting_name, 's')
        hints = fixups.to_python('SecretAgent', 'GetSecrets', 'hints', hints, 'as')
        return self.GetSecretsImpl(settings, connection, setting_name, hints, flags)


# These two are interfaces that must be provided to NetworkManager. Keep them
# as comments for documentation purposes.
#
# class PPP(NMDbusInterface): pass
# class VPNPlugin(NMDbusInterface):
#     interface_names = ['org.freedesktop.NetworkManager.VPN.Plugin']

def const(prefix, val):
    prefix = f'NM_{prefix.upper()}_'
    for key, vval in globals().items():
        if 'REASON' in key and 'REASON' not in prefix:
            continue
        if key.startswith(prefix) and val == vval:
            return key.replace(prefix, '').lower()
    raise ValueError("No constant found for %s* with value %d", (prefix, val))


# Several fixer methods to make the data easier to handle in python
# - SSID sent/returned as bytes (only encoding tried is utf-8)
# - IP, Mac address and route metric encoding/decoding
class fixups(object):
    @staticmethod
    def to_dbus(cls, method, arg, val, signature):
        if arg in 'connection' 'properties' and signature == 'a{sa{sv}}':
            settings = copy.deepcopy(val)
            for key in settings:
                if 'mac-address' in settings[key]:
                    settings[key]['mac-address'] = fixups.mac_to_dbus(settings[key]['mac-address'])
                if 'cloned-mac-address' in settings[key]:
                    settings[key]['cloned-mac-address'] = fixups.mac_to_dbus(settings[key]['cloned-mac-address'])
                if 'bssid' in settings[key]:
                    settings[key]['bssid'] = fixups.mac_to_dbus(settings[key]['bssid'])
                for cert in ['ca-cert', 'client-cert', 'phase2-ca-cert', 'phase2-client-cert', 'private-key']:
                    if cert in settings[key]:
                        settings[key][cert] = fixups.cert_to_dbus(settings[key][cert])
                if 'routing-rules' in settings[key]:
                    for rule in settings[key]['routing-rules']:
                        for p in rule:
                            rule[p] = dbus.Int32(rule[p]) if p == 'family' else dbus.UInt32(rule[p])
                    settings[key]['routing-rules'] = dbus.Array(
                        settings[key]['routing-rules'], signature=dbus.Signature('a{sv}'))
            if 'ssid' in settings.get('802-11-wireless', {}):
                settings['802-11-wireless']['ssid'] = fixups.ssid_to_dbus(settings['802-11-wireless']['ssid'])
            with contextlib.suppress(KeyError):
                val['ipv4']['addresses'] = [fixups.addrconf_to_python(addr, socket.AF_INET) for addr in
                                            val['ipv4']['addresses']]
                val['ipv4']['routes'] = [fixups.route_to_python(route, socket.AF_INET) for route in
                                         val['ipv4']['routes']]
                val['ipv4']['dns'] = [fixups.addr_to_python(addr, socket.AF_INET) for addr in val['ipv4']['dns']]
                val['ipv6']['addresses'] = [fixups.addrconf_to_python(addr, socket.AF_INET6) for addr in
                                            val['ipv6']['addresses']]
                val['ipv6']['routes'] = [fixups.route_to_python(route, socket.AF_INET6) for route in
                                         val['ipv6']['routes']]
                val['ipv6']['dns'] = [fixups.addr_to_python(addr, socket.AF_INET6) for addr in val['ipv6']['dns']]
            # Get rid of empty arrays/dicts. dbus barfs on them (can't guess
            # signatures), and if they were to get through, NetworkManager
            # ignores them anyway.
            for key in list(settings.keys()):
                if isinstance(settings[key], dict):
                    for key2 in list(settings[key].keys()):
                        if settings[key][key2] in ({}, []):
                            del settings[key][key2]
                if settings[key] in ({}, []):
                    del settings[key]
            val = settings
        return fixups.base_to_dbus(val)

    @staticmethod
    def base_to_dbus(val):
        if isinstance(val, NMDbusInterface):
            return val.object_path
        if hasattr(val.__class__, 'mro'):
            for cls in val.__class__.mro():
                if cls.__module__ in ('dbus', '_dbus_bindings'):
                    return val
        if hasattr(val, '__iter__') and not isinstance(val, six.string_types):
            if hasattr(val, 'items'):
                return dict([(x, fixups.base_to_dbus(y)) for x, y in val.items()])
            else:
                return [fixups.base_to_dbus(x) for x in val]
        return val

    @staticmethod
    def to_python(cls, method, arg, val, signature):
        val = fixups.base_to_python(val)
        cls_af = {'IP4Config': socket.AF_INET, 'IP6Config': socket.AF_INET6}.get(cls, socket.AF_INET)
        if method == 'Get':
            if arg == 'Ip4Address':
                return fixups.addr_to_python(val, socket.AF_INET)
            if arg == 'Ip6Address':
                return fixups.addr_to_python(val, socket.AF_INET6)
            if arg == 'Ssid':
                return fixups.ssid_to_python(val)
            if arg == 'Strength':
                return fixups.strength_to_python(val)
            if arg == 'Addresses':
                return [fixups.addrconf_to_python(addr, cls_af) for addr in val]
            if arg == 'Routes':
                return [fixups.route_to_python(route, cls_af) for route in val]
            if arg in ('Nameservers', 'WinsServers'):
                return [fixups.addr_to_python(addr, cls_af) for addr in val]
            if arg == 'Options':
                for key in val:
                    if key.startswith('requested_'):
                        val[key] = bool(int(val[key]))
                    elif val[key].isdigit():
                        val[key] = int(val[key])
                    elif key in ('domain_name_servers', 'ntp_servers', 'routers'):
                        val[key] = val[key].split()

            return val
        if method == 'GetSettings':
            if 'ssid' in val.get('802-11-wireless', {}):
                val['802-11-wireless']['ssid'] = fixups.ssid_to_python(val['802-11-wireless']['ssid'])
            for key in val:
                val_ = val[key]
                if 'mac-address' in val_:
                    val_['mac-address'] = fixups.mac_to_python(val_['mac-address'])
                if 'cloned-mac-address' in val_:
                    val_['cloned-mac-address'] = fixups.mac_to_python(val_['cloned-mac-address'])
                if 'bssid' in val_:
                    val_['bssid'] = fixups.mac_to_python(val_['bssid'])
            if 'ipv4' in val:
                if 'addresses' in val['ipv4']:
                    val['ipv4']['addresses'] = [fixups.addrconf_to_python(addr, socket.AF_INET) for addr in
                                                val['ipv4']['addresses']]
                if 'routes' in val['ipv4']:
                    val['ipv4']['routes'] = [fixups.route_to_python(route, socket.AF_INET) for route in
                                             val['ipv4']['routes']]
                if 'dns' in val['ipv4']:
                    val['ipv4']['dns'] = [fixups.addr_to_python(addr, socket.AF_INET) for addr in val['ipv4']['dns']]
            if 'ipv6' in val:
                if 'addresses' in val['ipv6']:
                    val['ipv6']['addresses'] = [fixups.addrconf_to_python(addr, socket.AF_INET6) for addr in
                                                val['ipv6']['addresses']]
                if 'routes' in val['ipv6']:
                    val['ipv6']['routes'] = [fixups.route_to_python(route, socket.AF_INET6) for route in
                                             val['ipv6']['routes']]
                if 'dns' in val['ipv6']:
                    val['ipv6']['dns'] = [fixups.addr_to_python(addr, socket.AF_INET6) for addr in val['ipv6']['dns']]
            return val
        if method == 'PropertiesChanged':
            for prop in val:
                val[prop] = fixups.to_python(cls, 'Get', prop, val[prop], None)
        return val

    @staticmethod
    def base_to_python(val):
        if isinstance(val, dbus.ByteArray):
            return "".join([str(x) for x in val])
        if isinstance(val, (dbus.Array, list, tuple)):
            return [fixups.base_to_python(x) for x in val]
        if isinstance(val, (dbus.Dictionary, dict)):
            return dict([(fixups.base_to_python(x), fixups.base_to_python(y)) for x, y in val.items()])
        if isinstance(val, dbus.ObjectPath):
            for obj in (NetworkManager, Settings, AgentManager):
                if val == obj.object_path:
                    return obj
            if val.startswith('/org/freedesktop/NetworkManager/'):
                classname = val.split('/')[4]
                classname = {
                    'Settings': 'Connection',
                    'Devices': 'Device',
                }.get(classname, classname)
                return globals()[classname](val)
            if val == '/':
                return None
        if isinstance(val, (dbus.Signature, dbus.String)):
            return six.text_type(val)
        if isinstance(val, dbus.Boolean):
            return bool(val)
        if isinstance(val, (dbus.Int16, dbus.UInt16, dbus.Int32, dbus.UInt32, dbus.Int64, dbus.UInt64)):
            return int(val)
        return six.int2byte(int(val)) if isinstance(val, dbus.Byte) else val

    @staticmethod
    def ssid_to_python(ssid):
        try:
            return bytes().join(ssid).decode('utf-8')
        except UnicodeDecodeError:
            ssid = bytes().join(ssid).decode('utf-8', 'replace')
            warnings.warn(f"Unable to decode ssid {ssid} properly", UnicodeWarning)
            return ssid

    @staticmethod
    def ssid_to_dbus(ssid):
        if isinstance(ssid, six.text_type):
            ssid = ssid.encode('utf-8')
        return [dbus.Byte(x) for x in ssid]

    @staticmethod
    def strength_to_python(strength):
        return struct.unpack('B', strength)[0]

    @staticmethod
    def mac_to_python(mac):
        return "%02X:%02X:%02X:%02X:%02X:%02X" % tuple(ord(x) for x in mac)

    @staticmethod
    def mac_to_dbus(mac):
        return [dbus.Byte(int(x, 16)) for x in mac.split(':')]

    @staticmethod
    def addrconf_to_python(addrconf, family):
        addr, netmask, gateway = addrconf
        return [
            fixups.addr_to_python(addr, family),
            netmask,
            fixups.addr_to_python(gateway, family)
        ]

    @staticmethod
    def addrconf_to_dbus(addrconf, family):
        addr, netmask, gateway = addrconf
        if family == socket.AF_INET:
            return [
                fixups.addr_to_dbus(addr, family),
                fixups.mask_to_dbus(netmask),
                fixups.addr_to_dbus(gateway, family)
            ]
        else:
            return dbus.Struct(
                (
                    fixups.addr_to_dbus(addr, family),
                    fixups.mask_to_dbus(netmask),
                    fixups.addr_to_dbus(gateway, family)
                ), signature='ayuay'
            )

    @staticmethod
    def addr_to_python(addr, family):
        if family == socket.AF_INET:
            return socket.inet_ntop(family, struct.pack('I', addr))
        else:
            return socket.inet_ntop(family, b''.join(addr))

    @staticmethod
    def addr_to_dbus(addr, family):
        if family == socket.AF_INET:
            return dbus.UInt32(struct.unpack('I', socket.inet_pton(family, addr))[0])
        else:
            return dbus.ByteArray(socket.inet_pton(family, addr))

    @staticmethod
    def mask_to_dbus(mask):
        return dbus.UInt32(mask)

    @staticmethod
    def route_to_python(route, family):
        addr, netmask, gateway, metric = route
        return [
            fixups.addr_to_python(addr, family),
            netmask,
            fixups.addr_to_python(gateway, family),
            metric
        ]

    @staticmethod
    def route_to_dbus(route, family):
        addr, netmask, gateway, metric = route
        return [
            fixups.addr_to_dbus(addr, family),
            fixups.mask_to_dbus(netmask),
            fixups.addr_to_dbus(gateway, family),
            metric
        ]

    @staticmethod
    def cert_to_dbus(cert):
        if not isinstance(cert, bytes):
            if not cert.startswith('file://'):
                cert = f'file://{cert}'
            cert = cert.encode('utf-8') + b'\0'
        return [dbus.Byte(x) for x in cert]


# Turn NetworkManager and Settings into singleton objects
NetworkManager = NetworkManager()
Settings = Settings()
AgentManager = AgentManager()
init_bus.close()
del init_bus
del xml_cache

# Constants below are generated with makeconstants.py. Do not edit manually.
NM_CAPABILITY_TEAM = 1
NM_CAPABILITY_OVS = 2
NM_STATE_UNKNOWN = 0
NM_STATE_ASLEEP = 10
NM_STATE_DISCONNECTED = 20
NM_STATE_DISCONNECTING = 30
NM_STATE_CONNECTING = 40
NM_STATE_CONNECTED_LOCAL = 50
NM_STATE_CONNECTED_SITE = 60
NM_STATE_CONNECTED_GLOBAL = 70
NM_CONNECTIVITY_UNKNOWN = 0
NM_CONNECTIVITY_NONE = 1
NM_CONNECTIVITY_PORTAL = 2
NM_CONNECTIVITY_LIMITED = 3
NM_CONNECTIVITY_FULL = 4
NM_DEVICE_TYPE_UNKNOWN = 0
NM_DEVICE_TYPE_ETHERNET = 1
NM_DEVICE_TYPE_WIFI = 2
NM_DEVICE_TYPE_UNUSED1 = 3
NM_DEVICE_TYPE_UNUSED2 = 4
NM_DEVICE_TYPE_BT = 5
NM_DEVICE_TYPE_OLPC_MESH = 6
NM_DEVICE_TYPE_WIMAX = 7
NM_DEVICE_TYPE_MODEM = 8
NM_DEVICE_TYPE_INFINIBAND = 9
NM_DEVICE_TYPE_BOND = 10
NM_DEVICE_TYPE_VLAN = 11
NM_DEVICE_TYPE_ADSL = 12
NM_DEVICE_TYPE_BRIDGE = 13
NM_DEVICE_TYPE_GENERIC = 14
NM_DEVICE_TYPE_TEAM = 15
NM_DEVICE_TYPE_TUN = 16
NM_DEVICE_TYPE_IP_TUNNEL = 17
NM_DEVICE_TYPE_MACVLAN = 18
NM_DEVICE_TYPE_VXLAN = 19
NM_DEVICE_TYPE_VETH = 20
NM_DEVICE_TYPE_MACSEC = 21
NM_DEVICE_TYPE_DUMMY = 22
NM_DEVICE_TYPE_PPP = 23
NM_DEVICE_TYPE_OVS_INTERFACE = 24
NM_DEVICE_TYPE_OVS_PORT = 25
NM_DEVICE_TYPE_OVS_BRIDGE = 26
NM_DEVICE_TYPE_WPAN = 27
NM_DEVICE_TYPE_6LOWPAN = 28
NM_DEVICE_TYPE_WIREGUARD = 29
NM_DEVICE_TYPE_WIFI_P2P = 30
NM_DEVICE_TYPE_VRF = 31
NM_DEVICE_CAP_NONE = 0
NM_DEVICE_CAP_NM_SUPPORTED = 1
NM_DEVICE_CAP_CARRIER_DETECT = 2
NM_DEVICE_CAP_IS_SOFTWARE = 4
NM_DEVICE_CAP_SRIOV = 8
NM_WIFI_DEVICE_CAP_NONE = 0
NM_WIFI_DEVICE_CAP_CIPHER_WEP40 = 1
NM_WIFI_DEVICE_CAP_CIPHER_WEP104 = 2
NM_WIFI_DEVICE_CAP_CIPHER_TKIP = 4
NM_WIFI_DEVICE_CAP_CIPHER_CCMP = 8
NM_WIFI_DEVICE_CAP_WPA = 16
NM_WIFI_DEVICE_CAP_RSN = 32
NM_WIFI_DEVICE_CAP_AP = 64
NM_WIFI_DEVICE_CAP_ADHOC = 128
NM_WIFI_DEVICE_CAP_FREQ_VALID = 256
NM_WIFI_DEVICE_CAP_FREQ_2GHZ = 512
NM_WIFI_DEVICE_CAP_FREQ_5GHZ = 1024
NM_WIFI_DEVICE_CAP_MESH = 4096
NM_WIFI_DEVICE_CAP_IBSS_RSN = 8192
NM_802_11_AP_FLAGS_NONE = 0
NM_802_11_AP_FLAGS_PRIVACY = 1
NM_802_11_AP_FLAGS_WPS = 2
NM_802_11_AP_FLAGS_WPS_PBC = 4
NM_802_11_AP_FLAGS_WPS_PIN = 8
NM_802_11_AP_SEC_NONE = 0
NM_802_11_AP_SEC_PAIR_WEP40 = 1
NM_802_11_AP_SEC_PAIR_WEP104 = 2
NM_802_11_AP_SEC_PAIR_TKIP = 4
NM_802_11_AP_SEC_PAIR_CCMP = 8
NM_802_11_AP_SEC_GROUP_WEP40 = 16
NM_802_11_AP_SEC_GROUP_WEP104 = 32
NM_802_11_AP_SEC_GROUP_TKIP = 64
NM_802_11_AP_SEC_GROUP_CCMP = 128
NM_802_11_AP_SEC_KEY_MGMT_PSK = 256
NM_802_11_AP_SEC_KEY_MGMT_802_1X = 512
NM_802_11_AP_SEC_KEY_MGMT_SAE = 1024
NM_802_11_AP_SEC_KEY_MGMT_OWE = 2048
NM_802_11_AP_SEC_KEY_MGMT_OWE_TM = 4096
NM_802_11_MODE_UNKNOWN = 0
NM_802_11_MODE_ADHOC = 1
NM_802_11_MODE_INFRA = 2
NM_802_11_MODE_AP = 3
NM_802_11_MODE_MESH = 4
NM_BT_CAPABILITY_NONE = 0
NM_BT_CAPABILITY_DUN = 1
NM_BT_CAPABILITY_NAP = 2
NM_DEVICE_MODEM_CAPABILITY_NONE = 0
NM_DEVICE_MODEM_CAPABILITY_POTS = 1
NM_DEVICE_MODEM_CAPABILITY_CDMA_EVDO = 2
NM_DEVICE_MODEM_CAPABILITY_GSM_UMTS = 4
NM_DEVICE_MODEM_CAPABILITY_LTE = 8
NM_WIMAX_NSP_NETWORK_TYPE_UNKNOWN = 0
NM_WIMAX_NSP_NETWORK_TYPE_HOME = 1
NM_WIMAX_NSP_NETWORK_TYPE_PARTNER = 2
NM_WIMAX_NSP_NETWORK_TYPE_ROAMING_PARTNER = 3
NM_DEVICE_STATE_UNKNOWN = 0
NM_DEVICE_STATE_UNMANAGED = 10
NM_DEVICE_STATE_UNAVAILABLE = 20
NM_DEVICE_STATE_DISCONNECTED = 30
NM_DEVICE_STATE_PREPARE = 40
NM_DEVICE_STATE_CONFIG = 50
NM_DEVICE_STATE_NEED_AUTH = 60
NM_DEVICE_STATE_IP_CONFIG = 70
NM_DEVICE_STATE_IP_CHECK = 80
NM_DEVICE_STATE_SECONDARIES = 90
NM_DEVICE_STATE_ACTIVATED = 100
NM_DEVICE_STATE_DEACTIVATING = 110
NM_DEVICE_STATE_FAILED = 120
NM_DEVICE_STATE_REASON_NONE = 0
NM_DEVICE_STATE_REASON_UNKNOWN = 1
NM_DEVICE_STATE_REASON_NOW_MANAGED = 2
NM_DEVICE_STATE_REASON_NOW_UNMANAGED = 3
NM_DEVICE_STATE_REASON_CONFIG_FAILED = 4
NM_DEVICE_STATE_REASON_IP_CONFIG_UNAVAILABLE = 5
NM_DEVICE_STATE_REASON_IP_CONFIG_EXPIRED = 6
NM_DEVICE_STATE_REASON_NO_SECRETS = 7
NM_DEVICE_STATE_REASON_SUPPLICANT_DISCONNECT = 8
NM_DEVICE_STATE_REASON_SUPPLICANT_CONFIG_FAILED = 9
NM_DEVICE_STATE_REASON_SUPPLICANT_FAILED = 10
NM_DEVICE_STATE_REASON_SUPPLICANT_TIMEOUT = 11
NM_DEVICE_STATE_REASON_PPP_START_FAILED = 12
NM_DEVICE_STATE_REASON_PPP_DISCONNECT = 13
NM_DEVICE_STATE_REASON_PPP_FAILED = 14
NM_DEVICE_STATE_REASON_DHCP_START_FAILED = 15
NM_DEVICE_STATE_REASON_DHCP_ERROR = 16
NM_DEVICE_STATE_REASON_DHCP_FAILED = 17
NM_DEVICE_STATE_REASON_SHARED_START_FAILED = 18
NM_DEVICE_STATE_REASON_SHARED_FAILED = 19
NM_DEVICE_STATE_REASON_AUTOIP_START_FAILED = 20
NM_DEVICE_STATE_REASON_AUTOIP_ERROR = 21
NM_DEVICE_STATE_REASON_AUTOIP_FAILED = 22
NM_DEVICE_STATE_REASON_MODEM_BUSY = 23
NM_DEVICE_STATE_REASON_MODEM_NO_DIAL_TONE = 24
NM_DEVICE_STATE_REASON_MODEM_NO_CARRIER = 25
NM_DEVICE_STATE_REASON_MODEM_DIAL_TIMEOUT = 26
NM_DEVICE_STATE_REASON_MODEM_DIAL_FAILED = 27
NM_DEVICE_STATE_REASON_MODEM_INIT_FAILED = 28
NM_DEVICE_STATE_REASON_GSM_APN_FAILED = 29
NM_DEVICE_STATE_REASON_GSM_REGISTRATION_NOT_SEARCHING = 30
NM_DEVICE_STATE_REASON_GSM_REGISTRATION_DENIED = 31
NM_DEVICE_STATE_REASON_GSM_REGISTRATION_TIMEOUT = 32
NM_DEVICE_STATE_REASON_GSM_REGISTRATION_FAILED = 33
NM_DEVICE_STATE_REASON_GSM_PIN_CHECK_FAILED = 34
NM_DEVICE_STATE_REASON_FIRMWARE_MISSING = 35
NM_DEVICE_STATE_REASON_REMOVED = 36
NM_DEVICE_STATE_REASON_SLEEPING = 37
NM_DEVICE_STATE_REASON_CONNECTION_REMOVED = 38
NM_DEVICE_STATE_REASON_USER_REQUESTED = 39
NM_DEVICE_STATE_REASON_CARRIER = 40
NM_DEVICE_STATE_REASON_CONNECTION_ASSUMED = 41
NM_DEVICE_STATE_REASON_SUPPLICANT_AVAILABLE = 42
NM_DEVICE_STATE_REASON_MODEM_NOT_FOUND = 43
NM_DEVICE_STATE_REASON_BT_FAILED = 44
NM_DEVICE_STATE_REASON_GSM_SIM_NOT_INSERTED = 45
NM_DEVICE_STATE_REASON_GSM_SIM_PIN_REQUIRED = 46
NM_DEVICE_STATE_REASON_GSM_SIM_PUK_REQUIRED = 47
NM_DEVICE_STATE_REASON_GSM_SIM_WRONG = 48
NM_DEVICE_STATE_REASON_INFINIBAND_MODE = 49
NM_DEVICE_STATE_REASON_DEPENDENCY_FAILED = 50
NM_DEVICE_STATE_REASON_BR2684_FAILED = 51
NM_DEVICE_STATE_REASON_MODEM_MANAGER_UNAVAILABLE = 52
NM_DEVICE_STATE_REASON_SSID_NOT_FOUND = 53
NM_DEVICE_STATE_REASON_SECONDARY_CONNECTION_FAILED = 54
NM_DEVICE_STATE_REASON_DCB_FCOE_FAILED = 55
NM_DEVICE_STATE_REASON_TEAMD_CONTROL_FAILED = 56
NM_DEVICE_STATE_REASON_MODEM_FAILED = 57
NM_DEVICE_STATE_REASON_MODEM_AVAILABLE = 58
NM_DEVICE_STATE_REASON_SIM_PIN_INCORRECT = 59
NM_DEVICE_STATE_REASON_NEW_ACTIVATION = 60
NM_DEVICE_STATE_REASON_PARENT_CHANGED = 61
NM_DEVICE_STATE_REASON_PARENT_MANAGED_CHANGED = 62
NM_DEVICE_STATE_REASON_OVSDB_FAILED = 63
NM_DEVICE_STATE_REASON_IP_ADDRESS_DUPLICATE = 64
NM_DEVICE_STATE_REASON_IP_METHOD_UNSUPPORTED = 65
NM_DEVICE_STATE_REASON_SRIOV_CONFIGURATION_FAILED = 66
NM_DEVICE_STATE_REASON_PEER_NOT_FOUND = 67
NM_METERED_UNKNOWN = 0
NM_METERED_YES = 1
NM_METERED_NO = 2
NM_METERED_GUESS_YES = 3
NM_METERED_GUESS_NO = 4
NM_CONNECTION_MULTI_CONNECT_DEFAULT = 0
NM_CONNECTION_MULTI_CONNECT_SINGLE = 1
NM_CONNECTION_MULTI_CONNECT_MANUAL_MULTIPLE = 2
NM_CONNECTION_MULTI_CONNECT_MULTIPLE = 3
NM_ACTIVE_CONNECTION_STATE_UNKNOWN = 0
NM_ACTIVE_CONNECTION_STATE_ACTIVATING = 1
NM_ACTIVE_CONNECTION_STATE_ACTIVATED = 2
NM_ACTIVE_CONNECTION_STATE_DEACTIVATING = 3
NM_ACTIVE_CONNECTION_STATE_DEACTIVATED = 4
NM_ACTIVE_CONNECTION_STATE_REASON_UNKNOWN = 0
NM_ACTIVE_CONNECTION_STATE_REASON_NONE = 1
NM_ACTIVE_CONNECTION_STATE_REASON_USER_DISCONNECTED = 2
NM_ACTIVE_CONNECTION_STATE_REASON_DEVICE_DISCONNECTED = 3
NM_ACTIVE_CONNECTION_STATE_REASON_SERVICE_STOPPED = 4
NM_ACTIVE_CONNECTION_STATE_REASON_IP_CONFIG_INVALID = 5
NM_ACTIVE_CONNECTION_STATE_REASON_CONNECT_TIMEOUT = 6
NM_ACTIVE_CONNECTION_STATE_REASON_SERVICE_START_TIMEOUT = 7
NM_ACTIVE_CONNECTION_STATE_REASON_SERVICE_START_FAILED = 8
NM_ACTIVE_CONNECTION_STATE_REASON_NO_SECRETS = 9
NM_ACTIVE_CONNECTION_STATE_REASON_LOGIN_FAILED = 10
NM_ACTIVE_CONNECTION_STATE_REASON_CONNECTION_REMOVED = 11
NM_ACTIVE_CONNECTION_STATE_REASON_DEPENDENCY_FAILED = 12
NM_ACTIVE_CONNECTION_STATE_REASON_DEVICE_REALIZE_FAILED = 13
NM_ACTIVE_CONNECTION_STATE_REASON_DEVICE_REMOVED = 14
NM_SECRET_AGENT_GET_SECRETS_FLAG_NONE = 0
NM_SECRET_AGENT_GET_SECRETS_FLAG_ALLOW_INTERACTION = 1
NM_SECRET_AGENT_GET_SECRETS_FLAG_REQUEST_NEW = 2
NM_SECRET_AGENT_GET_SECRETS_FLAG_USER_REQUESTED = 4
NM_SECRET_AGENT_GET_SECRETS_FLAG_WPS_PBC_ACTIVE = 8
NM_SECRET_AGENT_GET_SECRETS_FLAG_ONLY_SYSTEM = 2147483648
NM_SECRET_AGENT_GET_SECRETS_FLAG_NO_ERRORS = 1073741824
NM_IP_TUNNEL_MODE_UNKNOWN = 0
NM_IP_TUNNEL_MODE_IPIP = 1
NM_IP_TUNNEL_MODE_GRE = 2
NM_IP_TUNNEL_MODE_SIT = 3
NM_IP_TUNNEL_MODE_ISATAP = 4
NM_IP_TUNNEL_MODE_VTI = 5
NM_IP_TUNNEL_MODE_IP6IP6 = 6
NM_IP_TUNNEL_MODE_IPIP6 = 7
NM_IP_TUNNEL_MODE_IP6GRE = 8
NM_IP_TUNNEL_MODE_VTI6 = 9
NM_IP_TUNNEL_MODE_GRETAP = 10
NM_IP_TUNNEL_MODE_IP6GRETAP = 11
NM_CHECKPOINT_CREATE_FLAG_NONE = 0
NM_CHECKPOINT_CREATE_FLAG_DESTROY_ALL = 1
NM_CHECKPOINT_CREATE_FLAG_DELETE_NEW_CONNECTIONS = 2
NM_CHECKPOINT_CREATE_FLAG_DISCONNECT_NEW_DEVICES = 4
NM_CHECKPOINT_CREATE_FLAG_ALLOW_OVERLAPPING = 8
NM_ROLLBACK_RESULT_OK = 0
NM_ROLLBACK_RESULT_ERR_NO_DEVICE = 1
NM_ROLLBACK_RESULT_ERR_DEVICE_UNMANAGED = 2
NM_ROLLBACK_RESULT_ERR_FAILED = 3
NM_SETTINGS_CONNECTION_FLAG_NONE = 0
NM_SETTINGS_CONNECTION_FLAG_UNSAVED = 1
NM_SETTINGS_CONNECTION_FLAG_NM_GENERATED = 2
NM_SETTINGS_CONNECTION_FLAG_VOLATILE = 4
NM_SETTINGS_CONNECTION_FLAG_EXTERNAL = 8
NM_ACTIVATION_STATE_FLAG_NONE = 0
NM_ACTIVATION_STATE_FLAG_IS_MASTER = 1
NM_ACTIVATION_STATE_FLAG_IS_SLAVE = 2
NM_ACTIVATION_STATE_FLAG_LAYER2_READY = 4
NM_ACTIVATION_STATE_FLAG_IP4_READY = 8
NM_ACTIVATION_STATE_FLAG_IP6_READY = 16
NM_ACTIVATION_STATE_FLAG_MASTER_HAS_SLAVES = 32
NM_ACTIVATION_STATE_FLAG_LIFETIME_BOUND_TO_PROFILE_VISIBILITY = 64
NM_ACTIVATION_STATE_FLAG_EXTERNAL = 128
NM_SETTINGS_ADD_CONNECTION2_FLAG_NONE = 0
NM_SETTINGS_ADD_CONNECTION2_FLAG_TO_DISK = 1
NM_SETTINGS_ADD_CONNECTION2_FLAG_IN_MEMORY = 2
NM_SETTINGS_ADD_CONNECTION2_FLAG_BLOCK_AUTOCONNECT = 32
NM_SETTINGS_UPDATE2_FLAG_NONE = 0
NM_SETTINGS_UPDATE2_FLAG_TO_DISK = 1
NM_SETTINGS_UPDATE2_FLAG_IN_MEMORY = 2
NM_SETTINGS_UPDATE2_FLAG_IN_MEMORY_DETACHED = 4
NM_SETTINGS_UPDATE2_FLAG_IN_MEMORY_ONLY = 8
NM_SETTINGS_UPDATE2_FLAG_VOLATILE = 16
NM_SETTINGS_UPDATE2_FLAG_BLOCK_AUTOCONNECT = 32
NM_SETTINGS_UPDATE2_FLAG_NO_REAPPLY = 64
NM_TERNARY_DEFAULT = -1
NM_TERNARY_FALSE = 0
NM_TERNARY_TRUE = 1
NM_MANAGER_RELOAD_FLAG_NONE = 0
NM_MANAGER_RELOAD_FLAG_CONF = 1
NM_MANAGER_RELOAD_FLAG_DNS_RC = 2
NM_MANAGER_RELOAD_FLAG_DNS_FULL = 4
NM_MANAGER_RELOAD_FLAG_ALL = 7
NM_DEVICE_INTERFACE_FLAG_NONE = 0
NM_DEVICE_INTERFACE_FLAG_UP = 1
NM_DEVICE_INTERFACE_FLAG_LOWER_UP = 2
NM_DEVICE_INTERFACE_FLAG_CARRIER = 65536
NM_CLIENT_PERMISSION_NONE = 0
NM_CLIENT_PERMISSION_ENABLE_DISABLE_NETWORK = 1
NM_CLIENT_PERMISSION_ENABLE_DISABLE_WIFI = 2
NM_CLIENT_PERMISSION_ENABLE_DISABLE_WWAN = 3
NM_CLIENT_PERMISSION_ENABLE_DISABLE_WIMAX = 4
NM_CLIENT_PERMISSION_SLEEP_WAKE = 5
NM_CLIENT_PERMISSION_NETWORK_CONTROL = 6
NM_CLIENT_PERMISSION_WIFI_SHARE_PROTECTED = 7
NM_CLIENT_PERMISSION_WIFI_SHARE_OPEN = 8
NM_CLIENT_PERMISSION_SETTINGS_MODIFY_SYSTEM = 9
NM_CLIENT_PERMISSION_SETTINGS_MODIFY_OWN = 10
NM_CLIENT_PERMISSION_SETTINGS_MODIFY_HOSTNAME = 11
NM_CLIENT_PERMISSION_SETTINGS_MODIFY_GLOBAL_DNS = 12
NM_CLIENT_PERMISSION_RELOAD = 13
NM_CLIENT_PERMISSION_CHECKPOINT_ROLLBACK = 14
NM_CLIENT_PERMISSION_ENABLE_DISABLE_STATISTICS = 15
NM_CLIENT_PERMISSION_ENABLE_DISABLE_CONNECTIVITY_CHECK = 16
NM_CLIENT_PERMISSION_WIFI_SCAN = 17
NM_CLIENT_PERMISSION_LAST = 17
NM_CLIENT_PERMISSION_RESULT_UNKNOWN = 0
NM_CLIENT_PERMISSION_RESULT_YES = 1
NM_CLIENT_PERMISSION_RESULT_AUTH = 2
NM_CLIENT_PERMISSION_RESULT_NO = 3
NM_VPN_SERVICE_STATE_UNKNOWN = 0
NM_VPN_SERVICE_STATE_INIT = 1
NM_VPN_SERVICE_STATE_SHUTDOWN = 2
NM_VPN_SERVICE_STATE_STARTING = 3
NM_VPN_SERVICE_STATE_STARTED = 4
NM_VPN_SERVICE_STATE_STOPPING = 5
NM_VPN_SERVICE_STATE_STOPPED = 6
NM_VPN_CONNECTION_STATE_UNKNOWN = 0
NM_VPN_CONNECTION_STATE_PREPARE = 1
NM_VPN_CONNECTION_STATE_NEED_AUTH = 2
NM_VPN_CONNECTION_STATE_CONNECT = 3
NM_VPN_CONNECTION_STATE_IP_CONFIG_GET = 4
NM_VPN_CONNECTION_STATE_ACTIVATED = 5
NM_VPN_CONNECTION_STATE_FAILED = 6
NM_VPN_CONNECTION_STATE_DISCONNECTED = 7
NM_VPN_CONNECTION_STATE_REASON_UNKNOWN = 0
NM_VPN_CONNECTION_STATE_REASON_NONE = 1
NM_VPN_CONNECTION_STATE_REASON_USER_DISCONNECTED = 2
NM_VPN_CONNECTION_STATE_REASON_DEVICE_DISCONNECTED = 3
NM_VPN_CONNECTION_STATE_REASON_SERVICE_STOPPED = 4
NM_VPN_CONNECTION_STATE_REASON_IP_CONFIG_INVALID = 5
NM_VPN_CONNECTION_STATE_REASON_CONNECT_TIMEOUT = 6
NM_VPN_CONNECTION_STATE_REASON_SERVICE_START_TIMEOUT = 7
NM_VPN_CONNECTION_STATE_REASON_SERVICE_START_FAILED = 8
NM_VPN_CONNECTION_STATE_REASON_NO_SECRETS = 9
NM_VPN_CONNECTION_STATE_REASON_LOGIN_FAILED = 10
NM_VPN_CONNECTION_STATE_REASON_CONNECTION_REMOVED = 11
NM_VPN_PLUGIN_FAILURE_LOGIN_FAILED = 0
NM_VPN_PLUGIN_FAILURE_CONNECT_FAILED = 1
NM_VPN_PLUGIN_FAILURE_BAD_IP_CONFIG = 2
NM_SECRET_AGENT_ERROR_NOT_AUTHORIZED = 0
NM_SECRET_AGENT_ERROR_INVALID_CONNECTION = 1
NM_SECRET_AGENT_ERROR_USER_CANCELED = 2
NM_SECRET_AGENT_ERROR_AGENT_CANCELED = 3
NM_SECRET_AGENT_ERROR_INTERNAL_ERROR = 4
NM_SECRET_AGENT_ERROR_NO_SECRETS = 5
