from urllib import parse
from urllib.parse import urljoin
from bs4 import BeautifulSoup, Tag
from typing import TypedDict
import asyncio
import ssl

import aiohttp
import certifi

class PageData(TypedDict):
    url: str
    heading: str
    first_paragraph: str
    outgoing_links: list[str]
    image_urls: list[str]

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

def normalize_url(url: str) :
    split = parse.urlsplit(url)
    path = f"{split.netloc}{split.path}"
    path = path.rstrip("/")
    return path.lower()

def get_heading_from_html(html: str):
    soup = BeautifulSoup(html, "html.parser")
    h_tag = soup.h1
    return h_tag.get_text(strip=True) if isinstance(h_tag, Tag) else ""

def get_first_paragraph_from_html(html: str):
    soup = BeautifulSoup(html, "html.parser")

    main = soup.find("main")
    if isinstance(main, Tag):
        first_p = main.find("p")
    else:
        first_p = soup.find("p")

    return first_p.get_text(strip=True) if isinstance(first_p, Tag) else ""

def get_urls_from_html(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    urls = []
    for a_tag in soup.find_all("a"):
        href = a_tag.get("href")
        if href is None:
            continue
        urls.append(urljoin(base_url, href))
    return urls


def get_images_from_html(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    urls = []
    for img_tag in soup.find_all("img"):
        src = img_tag.get("src")
        if src is None:
            continue
        urls.append(urljoin(base_url, src))
    return urls

def extract_page_data(html: str, page_url: str) -> PageData:
    return {
        "url": page_url,
        "heading": get_heading_from_html(html),
        "first_paragraph": get_first_paragraph_from_html(html),
        "outgoing_links": get_urls_from_html(html, page_url),
        "image_urls": get_images_from_html(html, page_url),
    }
