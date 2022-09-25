from scrapper import LinkSpider


def scrape_hosts(ip):
    p = LinkSpider(ip, request_delay=0.2, max_depth=5)
    hosts = p.start(get_unique_hosts=True)
    return hosts
# dev.wifidog.org
# fonts.googleapis.com
# github.com
# 5.180.136.162:8000
