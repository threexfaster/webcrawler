import sys

from crawl import *
from json_report import write_json_report

DEFAULT_MAX_CONCURRENCY = 5
DEFAULT_MAX_PAGES = 500


def check_args():
    if len(sys.argv) < 2:
        print("no website provided")
        exit(1)
    if len(sys.argv) > 4:
        print("too many arguments provided")
        exit(1)
    print(f"starting crawl of: {sys.argv[1]}")
    return


async def main():
    check_args()
    base_url = sys.argv[1]
    max_concurrency = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_MAX_CONCURRENCY
    max_pages = int(sys.argv[3]) if len(sys.argv) > 3 else DEFAULT_MAX_PAGES
    page_data = await crawl_site_async(base_url, max_concurrency, max_pages)

    # print(f"\nfound {len(page_data)} pages:\n")
    # for data in page_data.values():
    #     print(data)
    write_json_report(page_data)

if __name__ == "__main__":
    asyncio.run(main())
