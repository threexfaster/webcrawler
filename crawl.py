import asyncio
import ssl
from types import TracebackType
from typing import TypedDict
from urllib.parse import urljoin, urlsplit

import aiohttp
import certifi
from bs4 import BeautifulSoup, Tag

class PageData(TypedDict):
    url: str
    heading: str
    first_paragraph: str
    outgoing_links: list[str]
    image_urls: list[str]

def normalize_url(url: str) -> str:
    split = urlsplit(url)
    path = f"{split.netloc}{split.path}"
    path = path.rstrip("/")
    return path.lower()

def get_heading_from_html(html: str):
    soup = BeautifulSoup(html, "html.parser")
    h_tag = soup.h1
    return h_tag.get_text(strip=True) if isinstance(h_tag, Tag) else ""

def get_first_paragraph_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    main = soup.find("main")
    if isinstance(main, Tag):
        first_p = main.find("p")
    else:
        first_p = soup.find("p")

    return first_p.get_text(strip=True) if isinstance(first_p, Tag) else ""

def get_urls_from_html(html: str, base_url: str) -> list[str]:
    urls = []
    soup = BeautifulSoup(html, "html.parser")

    for a_tag in soup.find_all("a"):
        if not isinstance(a_tag, Tag):
            continue
        href = a_tag.get("href")
        if isinstance(href, str) and href:
            try:
                urls.append(urljoin(base_url, href))
            except Exception as e:
                print(f"{str(e)}: {href}")
    return urls


def get_images_from_html(html: str, base_url:str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls = []
    for img_tag in soup.find_all("img"):
        if not isinstance(img_tag, Tag):
            continue
        src = img_tag.get("src")
        if isinstance(src, str) and src:
            try:
                urls.append(urljoin(base_url, src))
            except Exception as e:
                print(f"{str(e)}: {src}")
    return urls

def extract_page_data(html: str, page_url: str) -> PageData:
    return {
        "url": page_url,
        "heading": get_heading_from_html(html),
        "first_paragraph": get_first_paragraph_from_html(html),
        "outgoing_links": get_urls_from_html(html, page_url),
        "image_urls": get_images_from_html(html, page_url),
    }

class AsyncCrawler:
    def __init__(self, base_url: str, max_concurrency: int, max_pages: int):
        self.base_url = base_url
        self.base_domain = urlsplit(base_url).netloc
        self.page_data: dict[str, PageData] = {}
        self.visited: set[str] = set()
        self.lock = asyncio.Lock()
        self.max_concurrency = max_concurrency
        self.max_pages = max_pages
        self.semaphore = asyncio.Semaphore(self.max_concurrency)
        self.session: aiohttp.ClientSession | None = None
        self.should_stop = False
        self.all_tasks: set[asyncio.Task] = set()

    async def __aenter__(self):
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        self.session = aiohttp.ClientSession(connector=connector)
        return self

    async def __aexit__(
            self,
            exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: TracebackType | None
    ) -> None:
        if self.session is not None:
            await self.session.close()

    async def add_page_visit(self, normalized_url: str) -> bool:
        async with self.lock:
            if self.should_stop:
                return False

            if normalized_url in self.visited:
                return False

            if len(self.page_data) >= self.max_pages:
                self.should_stop = True
                print("Reached maximum number of pages to crawl.")
                for task in self.all_tasks:
                    task.cancel()
                return False

            self.visited.add(normalized_url)
            return True

    async def get_html(self, url: str) -> str | None:
        if self.session is None:
            print(f"Error: no active session for {url}")
            return None

        try:
            async with self.session.get(
                    url, headers={"User-Agent": "BootCrawler/1.0"}
            ) as response:
                if response.status > 399:
                    print(f"Error: HTTP {response.status} for {url}")
                    return None
                content_type = response.headers.get("content-type", "")
                if "text/html" not in content_type:
                    print(f"Error: Non-HTML content {content_type} for {url}")
                    return None

                return await response.text()
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None


    async def crawl_page(self, current_url):
        if self.should_stop:
            return

        if urlsplit(current_url).netloc != self.base_domain:
            return

        normalized_url = normalize_url(current_url)

        is_new_visit = await self.add_page_visit(normalized_url)
        if not is_new_visit:
            return

        async with self.semaphore:
            print(
                f"Crawling {current_url} (Active: {self.max_concurrency - self.semaphore._value})"
            )
            html = await self.get_html(current_url)

        if html is None:
            return

        page_data = extract_page_data(html, current_url)
        async with self.lock:
            if len(self.page_data) >= self.max_pages:
                return
            self.page_data[normalized_url] = page_data

        tasks = []
        for next_url in get_urls_from_html(html, current_url):
            task = asyncio.create_task(self.crawl_page(next_url))
            self.all_tasks.add(task)
            tasks.append(task)

        try:
            await asyncio.gather(*tasks)
        finally:
            for task in tasks:
                self.all_tasks.discard(task)

    async def crawl(self) -> dict[str, PageData]:
        try:
            await self.crawl_page(self.base_url)
        except asyncio.CancelledError:
            pass
        return self.page_data


async def crawl_site_async(base_url: str, max_concurrency: int, max_pages: int) -> dict[str, PageData]:
    async with AsyncCrawler(base_url, max_concurrency, max_pages) as crawler:
        return await crawler.crawl()