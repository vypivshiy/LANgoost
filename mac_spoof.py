# -*- coding: utf-8 -*-
# https://github.com/feross/SpoofMAC
import contextlib
import re
import subprocess
import sys
import os.path

__all__ = (
    'find_interfaces',
    'find_interface',
    'set_interface_mac',
    'wireless_port_names'
)

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
    """
    Linux platform specfic implementation for MAC spoofing.
    """

    def get_interface_mac(self, device):
        result = subprocess.check_output(["ip", "link", "show", device], stderr=subprocess.STDOUT,
                                         universal_newlines=True)
        m = re.search("(?<=\w\s)(.*)(?=\sbrd)", result)
        if not hasattr(m, "group") or m.group(0) == None:
            return None
        return m.group(0).strip()

    def find_interfaces(self, targets=None):
        """
        Returns the list of interfaces found on this machine as reported
        by the `ip` command.
        """
        targets = [t.lower() for t in targets] if targets else []
        # Parse the output of `ip` which gives
        # us 3 fields used:
        # - the adapter description
        # - the adapter name/device associated with this, if any,
        # - the MAC address, if any

        output = subprocess.check_output(["ip", "address"], stderr=subprocess.STDOUT, universal_newlines=True)

        # search for specific adapter gobble through mac address
        details = re.findall("^[\d]+:(.*)", output, re.MULTILINE)
        more_details = re.findall("[\s]+link(.*)", output, re.MULTILINE)

        # extract out ip address results from STDOUT (don't show loopback)
        for i in range(1, len(details)):
            description = None
            address = None
            adapter_name = None

            s = details[i].split(":")
            if len(s) >= 2:
                adapter_name = s[0].split()[0]

            info = more_details[i].split(" ")
            description = info[0].strip()[1:]
            address = info[1].strip()

            current_address = self.get_interface_mac(adapter_name)

            if not targets:
                # Not trying to match anything in particular,
                # return everything.
                yield description, adapter_name, address, current_address
                continue

            for target in targets:
                if target in (adapter_name.lower(), adapter_name.lower()):
                    yield description, adapter_name, address, current_address
                    break

    def find_interface(self, target):
        """
        Returns tuple of the first interface which matches `target`.
            adapter description, adapter name, mac address of target, current mac addr
        """
        try:
            return next(self.find_interfaces(targets=[target]))
        except StopIteration:
            pass

    def set_interface_mac(self, device, mac, port=None):
        """
        Set the device's mac address.  Handles shutting down and starting back up interface.
        """
        # turn off device
        cmd = "ip link set {} down".format(device)
        subprocess.call(cmd.split())
        # set mac
        cmd = "ip link set {} address {}".format(device, mac)
        subprocess.call(cmd.split())
        # turn on device
        cmd = "ip link set {} up".format(device)
        subprocess.call(cmd.split())


class LinuxSpoofer(OsSpoofer):
    """
    Linux platform specfic implementation for MAC spoofing.
    """

    def get_interface_mac(self, device):
        result = subprocess.check_output(["ifconfig", device], stderr=subprocess.STDOUT, universal_newlines=True)
        m = re.search("(?<=HWaddr\\s)(.*)", result)
        if not hasattr(m, "group") or m.group(0) == None:
            return None
        return m.group(0).strip()

    def find_interfaces(self, targets=None):
        """
        Returns the list of interfaces found on this machine as reported
        by the `ifconfig` command.
        """
        targets = [t.lower() for t in targets] if targets else []
        # Parse the output of `ifconfig` which gives
        # us 3 fields used:
        # - the adapter description
        # - the adapter name/device associated with this, if any,
        # - the MAC address, if any

        output = subprocess.check_output(["ifconfig"], stderr=subprocess.STDOUT, universal_newlines=True)

        # search for specific adapter gobble through mac address
        details = re.findall("(.*?)HWaddr(.*)", output, re.MULTILINE)

        # extract out ifconfig results from STDOUT
        for i in range(0, len(details)):
            description = None
            address = None
            adapter_name = None

            s = details[i][0].split(":")
            if len(s) >= 2:
                adapter_name = s[0].split()[0]
                description = s[1].strip()

            address = details[i][1].strip()

            current_address = self.get_interface_mac(adapter_name)

            if not targets:
                # Not trying to match anything in particular,
                # return everything.
                yield description, adapter_name, address, current_address
                continue

            for target in targets:
                if target in (adapter_name.lower(), adapter_name.lower()):
                    yield description, adapter_name, address, current_address
                    break

    def find_interface(self, target):
        """
        Returns tuple of the first interface which matches `target`.
            adapter description, adapter name, mac address of target, current mac addr
        """
        with contextlib.suppress(StopIteration):
            return next(self.find_interfaces(targets=[target]))

    def set_interface_mac(self, device, mac, port=None):
        """
        Set the device's mac address.  Handles shutting down and starting back up interface.
        """
        # turn off device & set mac
        cmd = f"ifconfig {device} down hw ether {mac}"
        subprocess.call(cmd.split())
        # turn on device
        cmd = f"ifconfig {device} up"
        subprocess.call(cmd.split())


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


def find_interfaces(targets=None):
    """
    Returns the list of interfaces found on this machine reported by the OS.
    Target varies by platform:
        MacOS & Linux this is the interface name in ifconfig or ip
        Windows this is the network adapter name in ipconfig
    """
    # Wrapper to interface handles encapsulating objects
    spoofer = get_os_spoofer()
    return spoofer.find_interfaces(targets)


def find_interface(targets=None):
    """
    Returns tuple of the first interface which matches `target`.
        adapter description, adapter name, mac address of target, current mac addr
    Target varies by platform:
        MacOS & Linux this is the interface name in ifconfig or ip
        Windows this is the network adapter name in ipconfig
    """
    # Wrapper to interface handles encapsulating objects
    spoofer = get_os_spoofer()
    return spoofer.find_interface(targets)


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
    for interface in find_interfaces():
        print(interface)
