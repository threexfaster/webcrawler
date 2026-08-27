import asyncio
import sys

from asynccrawler import crawl_site_async


def check_args():
    if len(sys.argv) < 2:
        print("no website provided")
        exit(1)
    if len(sys.argv) > 2:
        print("too many arguments provided")
        exit(1)
    print(f"starting crawl of: {sys.argv[1]}")
    return


async def main():
    check_args()
    base_url = sys.argv[1]
    page_data = await crawl_site_async(base_url)

    print(f"\nfound {len(page_data)} pages:\n")
    for data in page_data.values():
        if data is not None:
            print(data)


if __name__ == "__main__":
    asyncio.run(main())
