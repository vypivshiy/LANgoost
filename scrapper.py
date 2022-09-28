import re
from time import sleep
import logging
from typing import Literal, Union, Optional
from urllib.parse import urlparse, urljoin

import httpx
from httpx import Client, Response

logging.basicConfig(level=logging.DEBUG)

RE_HREF = re.compile(r'''href=['"](?P<path>.*?)['"]''')
RE_URL = re.compile(r'([/]{2}?[\d\w./\-?=;#&]+)')
RE_PSEUDO_JSON = re.compile(r'({"\w+".*});$')
REPLACE_JSON_CHARS = (r"\u002F", "/")


class LinkSpider:
    # todo add more
    IGNORE_EXTENSIONS = (
        ".png",
        ".gif",
        ".pdf",
        ".doc",
        ".docx",
        "xls",
        ".jpg",
        ".jpeg",
        ".css",
        ".js",
        ".svg",
        ".woff",
        "woff2",
        ".ico"
    )

    def __init__(self,
                 url_target: str,
                 *,
                 allow_redirects: bool = True,
                 protocol: Union[Literal["http"], Literal["https"]] = "https",
                 max_depth: int = 3,
                 request_delay: float = 0.3,
                 check_host_netloc: bool = True,
                 http2: bool = False,
                 timeout: float = 30):
        """
        :param url_target: start url target
        :param max_depth: max depth scrapping. default 3
        :param request_delay: request delay in seconds. default 0.3
        :param check_host_netloc: disable not target host parse. Default True
        """
        self.request_delay = request_delay
        self._protocol = protocol
        self._session = Client(http2=True) if http2 else Client()
        self._session.timeout = timeout
        self._session.headers.update(
            {
                "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.5112.126 Safari/537.36"})
        self._session.follow_redirects = allow_redirects

        self.base_url = url_target
        self._base_netloc = urlparse(url_target).netloc

        self.max_depth = max_depth
        self.check_host_netloc = check_host_netloc

        self._collected_links = set()
        self._scanned_links = set()

    def _normalize_url(self, url: str) -> str:
        if not url.startswith("http"):
            if url.startswith("//"):
                return f"{self._protocol}:{url}"
            if len(url.split(".")) > 1:
                return f"{self._protocol}://{url}"

            return urljoin(self.base_url, url.lstrip("//"))
        return url

    def _is_ignore_extension(self, url: str):
        return url.split("#")[0].endswith(self.IGNORE_EXTENSIONS)

    def _request(self, url: str, try_connects: int = 5) -> Optional[Response]:
        for i in range(try_connects):
            try:
                resp = self._session.get(url)
                sleep(self.request_delay)
            except httpx.UnsupportedProtocol:
                logging.error(f"Bad url {url}")
                return
            except Exception as e:
                logging.error(f"{e} retry connect {i}")
                sleep(self.request_delay)
                continue
            else:
                return resp
        raise ConnectionError("Retry connects was reached")

    def _url_extract(self, response: Response) -> set[str]:
        """url extractor"""
        all_urls = []
        # href url
        all_urls.extend(RE_HREF.findall(response.text))
        # all urls
        all_urls.extend(RE_URL.findall(response.text))

        # trying extract urls from json
        for data in RE_PSEUDO_JSON.findall(response.text):
            data = data.replace(*REPLACE_JSON_CHARS)
            all_urls.extend(RE_URL.findall(data))

        all_urls = [self._normalize_url(u) for u in all_urls if not self._is_ignore_extension(self._normalize_url(u))]
        urls = set(all_urls)

        self._collected_links.update(urls)
        return urls

    def _parse(self, url: str, depth: int) -> None:
        """recursive link parser method"""
        # ignore out of host
        if self.check_host_netloc and urlparse(url).netloc not in self._base_netloc:
            return
        if depth == self.max_depth:
            return
        if url in self._scanned_links:
            print("scanned")
            return
        logging.debug(f"depth [{depth}|{self.max_depth}] url={url} scrapped links [{len(self._collected_links)}]")
        resp = self._request(url)
        if not resp:
            return
        self._scanned_links.add(str(resp.url))
        if resp.status_code == 200:
            urls = self._url_extract(resp)
            for parsed_url in urls:
                self._parse(parsed_url, depth + 1)
        return

    def start(self, get_unique_hosts: bool = False) -> list[str]:
        self._parse(self.base_url, 0)
        if get_unique_hosts:
            return sorted([urlparse(u).netloc.lstrip("www.") for u in self._collected_links if u.startswith("http")])
        return sorted([u for u in self._collected_links if u.startswith("http")])


if __name__ == '__main__':
    p = LinkSpider("https://megafon.ru",
                   allow_redirects=True,
                   request_delay=0.5,
                   max_depth=2,
                   protocol="https",
                   http2=False)

    hosts = p.start()
    print(*hosts, sep="\n")
