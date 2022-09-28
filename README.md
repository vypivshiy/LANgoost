# LANGoost
[Base bypass methods instructions](README_bypass_methods.md)
# Module docs
[scrapper.py](scrapper.py)

Simple one-threaded, recursion spider for parse urls. Can parametrize scan depth and other settings.

Return sorted list urls or hosts 

```python
from scrapper import LinkSpider

spider = LinkSpider("https://requests.readthedocs.io/",
                    max_depth=1,
                    )
urls = spider.start()
print(len(urls))
print(*urls, sep="\n")
# 147
# https://api.github.com/user&#39;
# https://docutils.sourceforge.net/
# https://ghbtns.com/github-btn.html?user=psf&repo=requests&type=watch&count=true&size=large
# https://gist.github.com/973705
# https://github.com/psf/requests
# ...
```

[mac_spoof.py](mac_spoof.py)

*unix and macOS modules for obtaining MAC addresses of devices based on calling commands to the terminal 
and replacing the mac address with the specified one. Requires **root** privileges

```python
from mac_spoof import LinuxSpooferIP
for interface in LinuxSpooferIP().find_interfaces():
    print(interface)
# {'num': '1', 'interface_name': 'lo', 'type': 'loopback', 'mac': '00:00:00:00:00:00', 'inet': '127.0.0.1/8', 'valid_lft': 'forever', 'inet6': '::1/128'}
# {'num': '2', 'interface_name': 'wlp2s0', 'type': 'ether', 'mac': '00:ab:ba:f0:00:12', 'inet': '192.168.0.105/24', 'valid_lft': '3852sec', 'inet6': '2a02:2168:ad4a:cb00:232f:87f9:9817:b7a6/64'}
```

[mac_spoof.sh](mac_spoof.sh)

hackaptive.sh from kali linux 

[cellhack.py](cellhack.py)

PoC implementation of mac spoof, cellhack methods
