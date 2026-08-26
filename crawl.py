from urllib import parse
from urllib.parse import urljoin
from bs4 import BeautifulSoup, Tag

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