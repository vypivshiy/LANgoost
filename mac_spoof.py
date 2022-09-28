# -*- coding: utf-8 -*-
# based on https://github.com/feross/SpoofMAC
import contextlib
import re
import subprocess
import sys
import os.path


from typing import Optional, List, Literal, Generator, Dict

MAC_ADDRESS_R = re.compile(r"""
    ([0-9A-F]{1,2})[:-]?
    ([0-9A-F]{1,2})[:-]?
    ([0-9A-F]{1,2})[:-]?
    ([0-9A-F]{1,2})[:-]?
    ([0-9A-F]{1,2})[:-]?
    ([0-9A-F]{1,2})
    """, re.I | re.VERBOSE)

# The possible port names for wireless devices as returned by networksetup.
wireless_port_names = ('wi-fi', 'airport')


class OsSpoofer(object):
    """
    Abstract class for OS level MAC spoofing.
    """

    def find_interfaces(self, target):
        raise NotImplementedError("find_interfaces must be implemented")

    def find_interface(self, target):
        raise NotImplementedError("find_interface must be implemented")

    def get_interface_mac(self, device):
        raise NotImplementedError("get_interface_mac must be implemented")

    def set_interface_mac(self, device, mac, port=None):
        raise NotImplementedError("set_interface_mac must be implemented")


class LinuxSpooferIP(OsSpoofer):
    """Linux platform specfic implementation for MAC spoofing."""
    # parse mac interface from command $ip link show <device>
    RE_INTERFACE_MAC = re.compile(r"(?<=\w\s)(?P<mac>[a-fA-f\d:]+)(?=\sbrd)")
    # parse detail info from command $ip address
    RE_INTERFACES = re.compile(r"""(?P<num>\d+): (?P<interface_name>\w+): .*
\s*link/(?P<type>\w+) (?P<mac>[a-fA-f\d:]+)(?=\sbrd).*
\s*inet (?P<inet>[\d/.]+) .*
\s*valid_lft (?P<valid_lft>\w+) .*
\s*inet6 (?P<inet6>[a-fA-f\d:/]+) .*""")

    def get_interface_mac(self, device: str) -> str:
        """ Get mac address interface

        :param device: device name
        """
        result = subprocess.check_output(["ip", "link", "show", device], stderr=subprocess.STDOUT,
                                         universal_newlines=True)
        if mac := self.RE_INTERFACE_MAC.search(result):
            return mac.groupdict().get("mac")
        raise RuntimeError(f"Error parse mac address from {device}")

    def find_interfaces(self,
                        show_loopback: bool = True,
                        **kwargs) -> Generator[dict, None, None]:
        """Returns the generator of interfaces found on this machine as reported by the `ip` command.

        :param show_loopback: return loopback interface. Default False
        """
        output = subprocess.check_output(["ip", "address"], stderr=subprocess.STDOUT, universal_newlines=True)

        for n, result in enumerate(self.RE_INTERFACES.finditer(output)):
            if not show_loopback and n == 0:
                continue
            yield result.groupdict()

    def find_interface(self, target: str) -> NotImplemented:
        """
        Returns tuple of the first interface which matches `target`.
            adapter description, adapter name, mac address of target, current mac addr
        """
        raise NotImplementedError

    def set_interface_mac(self, device: str, mac: str, port=None) -> Literal[True]:
        """Set the device's mac address.  Handles shutting down and starting back up interface. Need run with sudo
        """
        # turn off device
        subprocess.call(f"ip link set {device} down")
        # set mac
        subprocess.call(f"ip link set {device} address {mac}")
        # turn on device
        subprocess.call(f"ip link set {device} up")
        return True


class LinuxSpoofer(OsSpoofer):
    """Linux platform specfic implementation for MAC spoofing."""
    # parse from command $ifconfig
    RE_INTERFACES = re.compile(r"""(?P<interface>^\w+): .*
\s*inet (?P<inet>[\d.]+)\s*netmask (?P<netmask>[\d.]+)\s*broadcast (?P<broadcast>[\d.]+)
\s*inet6 (?P<inet6>[a-fA-f\d:]+).*
\s*inet6 (?P<inet6_2>[a-fA-f\d:]+).*
\s*ether (?P<mac>[a-fA-f\d:]+).*""")

    def get_interface_mac(self, device: str) -> dict:
        result = subprocess.check_output(["ifconfig", device], stderr=subprocess.STDOUT, universal_newlines=True)
        if result := self.RE_INTERFACES.search(result):
            return result.groupdict()
        raise RuntimeError(f"Error parse mac address from {device}")

    def find_interfaces(self, **kwargs) -> Generator[dict, None, None]:
        """
        Returns the list of interfaces found on this machine as reported
        by the `ifconfig` command.
        """

        output = subprocess.check_output(["ifconfig"], stderr=subprocess.STDOUT, universal_newlines=True)

        for result in self.RE_INTERFACES.finditer(output):
            yield result.groupdict()

    def find_interface(self, target) -> NotImplemented:
        """
        Returns tuple of the first interface which matches `target`.
            adapter description, adapter name, mac address of target, current mac addr
        """
        raise NotImplementedError

    def set_interface_mac(self, device: str, mac: str, port=None):
        """
        Set the device's mac address.  Handles shutting down and starting back up interface.
        """
        # turn off device & set mac
        subprocess.call(f"ifconfig {device} down hw ether {mac}")
        # turn on device
        subprocess.call(f"ifconfig {device} up")


class MacSpoofer(OsSpoofer):
    """
    OS X platform specfic implementation for MAC spoofing.
    """

    # Path to Airport binary. This works on 10.7 and 10.8, but might be different
    # on older OS X versions.
    PATH_TO_AIRPORT = (
        '/System/Library/PrivateFrameworks/Apple80211.framework/Resources/airport'
    )

    def find_interfaces(self, targets=None):
        """
        Returns the list of interfaces found on this machine as reported
        by the `networksetup` command.
        """
        targets = [t.lower() for t in targets] if targets else []
        # Parse the output of `networksetup -listallhardwareports` which gives
        # us 3 fields per port:
        # - the port name,
        # - the device associated with this port, if any,
        # - The MAC address, if any, otherwise 'N/A'
        details = re.findall(
            r'^(?:Hardware Port|Device|Ethernet Address): (.+)$',
            subprocess.check_output((
                'networksetup',
                '-listallhardwareports'
            ), universal_newlines=True), re.MULTILINE
        )
        # Split the results into chunks of 3 (for our three fields) and yield
        # those that match `targets`.
        for i in range(0, len(details), 3):
            port, device, address = details[i:i + 3]

            address = MAC_ADDRESS_R.match(address.upper())
            if address:
                address = address.group(0)

            current_address = self.get_interface_mac(device)

            if not targets:
                # Not trying to match anything in particular,
                # return everything.
                yield port, device, address, current_address
                continue

            for target in targets:
                if target in (port.lower(), device.lower()):
                    yield port, device, address, current_address
                    break

    def find_interface(self, target):
        """
        Returns the first interface which matches `target`.
        """
        try:
            return next(self.find_interfaces(targets=[target]))
        except StopIteration:
            pass

    def set_interface_mac(self, device, mac, port):
        """
        Sets the mac address for `device` to `mac`.
        """
        if port.lower() in wireless_port_names:
            # Turn on the device, assuming it's an airport device.
            subprocess.call([
                'networksetup',
                '-setairportpower',
                device,
                'on'
            ])

        # For some reason this seems to be required even when changing a
        # non-airport device.
        subprocess.check_call([
            MacSpoofer.PATH_TO_AIRPORT,
            '-z'
        ])

        # Change the MAC.
        subprocess.check_call([
            'ifconfig',
            device,
            'ether',
            mac
        ])

        # Associate airport with known network (if any)
        subprocess.check_call([
            'networksetup',
            '-detectnewhardware'
        ])

    def get_interface_mac(self, device):
        """
        Returns currently-set MAC address of given interface. This is
        distinct from the interface's hardware MAC address.
        """

        try:
            result = subprocess.check_output([
                'ifconfig',
                device
            ], stderr=subprocess.STDOUT, universal_newlines=True)
        except subprocess.CalledProcessError:
            return None

        address = MAC_ADDRESS_R.search(result.upper())
        if address:
            address = address.group(0)

        return address


def get_os_spoofer():
    """
    OsSpoofer factory initializes approach OS platform dependent spoofer.
    """
    if 'darwin' in sys.platform:
        spoofer = MacSpoofer()
    elif sys.platform.startswith('linux'):
        if os.path.exists("/usr/bin/ip") or os.path.exists("/bin/ip"):
            spoofer = LinuxSpooferIP()
        else:
            spoofer = LinuxSpoofer()
    else:
        raise NotImplementedError()

    return spoofer


def find_interfaces():
    """
    Returns the list of interfaces found on this machine reported by the OS.
    Target varies by platform:
        MacOS & Linux this is the interface name in ifconfig or ip
        Windows this is the network adapter name in ipconfig
    """
    # Wrapper to interface handles encapsulating objects
    spoofer = get_os_spoofer()
    return spoofer.find_interfaces()


def find_interface():
    """
    Returns tuple of the first interface which matches `target`.
        adapter description, adapter name, mac address of target, current mac addr
    Target varies by platform:
        MacOS & Linux this is the interface name in ifconfig or ip
        Windows this is the network adapter name in ipconfig
    """
    # Wrapper to interface handles encapsulating objects
    return


def set_interface_mac(device, mac, port=None):
    """
    Sets the mac address for given `device` to `mac`.
    Device varies by platform:
        MacOS & Linux this is the interface name in ifconfig or ip
        Windows this is the network adapter name in ipconfig
    """
    # Wrapper to interface handles encapsulating objects
    spoofer = get_os_spoofer()
    spoofer.set_interface_mac(device, mac, port)


if __name__ == '__main__':
    for interface in LinuxSpooferIP().find_interfaces():
        print(interface)
