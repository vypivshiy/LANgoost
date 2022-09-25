import re
from time import sleep
import logging
from traceback import print_tb
from urllib.parse import urlparse

from httpx import Client


RE_HREF = re.compile(r'''href=['"](?P<path>.*?)['"]''')
RE_URL = re.compile(r'''['"](https?://.*?)['"]''')
logging.basicConfig(level=logging.DEBUG)


class LinkSpider:
    # todo add more
    IGNORE_EXTENSIONS = (
        ".png",
        ".gif",
        ".jpg",
        ".jpeg",
        ".css",
        ".js",
        ".svg"
    )

    def __init__(self,
                 url_target: str,
                 *,
                 allow_redirects: bool = True,
                 max_depth: int = 3,
                 request_delay: float = 0.3,
                 check_host_netloc: bool = True):
        """
        :param url_target: start url target
        :param max_depth: max depth scrapping. default 3
        :param request_delay: request delay in seconds. default 0.3
        :param check_host_netloc: disable not target host parse. Default True
        """
        self.request_delay = request_delay

        self._session = Client()
        self._session.headers.update(
            {"user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.5112.126 Safari/537.36"})
        self._session.event_hooks.update(
            {"response": [lambda resp: sleep(self.request_delay)]})
        self._session.follow_redirects = allow_redirects

        self._collected_links = set()
        self.max_depth = max_depth
        self.url = url_target
        self.check_host_netloc = check_host_netloc
        self._base_netloc = urlparse(self.url).netloc
        self._scanning_links = set()

    def _normalize_url(self, url: str) -> str:
        if not url.startswith("http"):
            if len(url.split(".")) > 1:
                return f"https://{url}"

            return self.url + url if url.startswith("/") else f"{self.url}/{url}"
        return url

    def _parse(self, url: str, depth: int) -> None:
        """recursive link parser method"""

        if url.endswith(self.IGNORE_EXTENSIONS):
            return

        if self.check_host_netloc and urlparse(url).netloc != self._base_netloc:
            return

        if depth == self.max_depth or url in self._scanning_links:
            return

        resp = self._session.get(url)
        self._scanning_links.add(resp.url)
        if resp.status_code == 200:
            urls = RE_HREF.findall(resp.text)
            urls = [self._normalize_url(u) for u in urls]
            urls = set(urls)

            self._collected_links.update(urls)
            for parsed_url in urls:
                self._parse(parsed_url, depth+1)
        return

    def start(self, get_unique_hosts: bool = False) -> set[str]:
        self._parse(self.url, 0)
        if get_unique_hosts:
            return [{urlparse(u).netloc.lstrip("www.") for u in self._collected_links}, self._collected_links]
        return self._collected_links


if __name__ == '__main__':
    p = LinkSpider("http://5.180.136.162:8000", request_delay=0.2, max_depth=5)
    hosts = p.start(get_unique_hosts=True)
