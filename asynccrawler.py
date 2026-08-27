import asyncio
import ssl
from urllib import parse

import aiohttp
import certifi

from crawl import normalize_url, get_urls_from_html, extract_page_data


class AsyncCrawler:
    def __init__(self, base_url, max_concurrency=5):
        self.base_url = base_url
        self.base_domain = parse.urlsplit(base_url).netloc
        self.page_data = {}
        self.lock = asyncio.Lock()
        self.max_concurrency = max_concurrency
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.session = None

    async def __aenter__(self):
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        self.session = aiohttp.ClientSession(connector=connector)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.close()

    async def add_page_visit(self, normalized_url):
        async with self.lock:
            if normalized_url in self.page_data:
                return False
            self.page_data[normalized_url] = None
            return True

    async def get_html(self, url):
        async with self.session.get(url, headers={"User-Agent": "BootCrawler/1.0"}) as response:
            response.raise_for_status()

            content_type = response.headers.get("Content-Type", "")
            if "text/html" not in content_type:
                raise Exception(f"got non-HTML content-type: {content_type}")

            return await response.text()

    async def crawl_page(self, current_url):
        if parse.urlsplit(current_url).netloc != self.base_domain:
            return

        normalized_url = normalize_url(current_url)
        is_new_visit = await self.add_page_visit(normalized_url)
        if not is_new_visit:
            return

        async with self.semaphore:
            print(f"crawling {current_url}")
            try:
                html = await self.get_html(current_url)
            except Exception as e:
                print(f"error crawling {current_url}: {e}")
                return

        page_data = extract_page_data(html, current_url)
        async with self.lock:
            self.page_data[normalized_url] = page_data

        tasks = [
            asyncio.create_task(self.crawl_page(next_url))
            for next_url in get_urls_from_html(html, current_url)
        ]
        await asyncio.gather(*tasks)

    async def crawl(self):
        await self.crawl_page(self.base_url)
        return self.page_data


async def crawl_site_async(base_url, max_concurrency=5):
    async with AsyncCrawler(base_url, max_concurrency) as crawler:
        return await crawler.crawl()
