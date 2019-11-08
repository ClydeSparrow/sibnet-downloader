import re
import argparse
import asyncio
import aiohttp

from contextlib import closing
from tqdm import tqdm

ID_REGEX = r".*\.php\?videoid=([0-9]*)"
TITLE_REGEX = r"videoName\'>(.*)<\/h1>"
URL_REGEX = r"\/v\/.+\d+.mp4"

HOST = "https://video.sibnet.ru"
USER_AGENT = "Mozilla/5.0 (Linux; Android 7.1.2; AFTMM Build/NS6265; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/70.0.3538.110 Mobile Safari/537.36"

DEFAULT_PARALLEL = 2
CHUNK_SIZE = 128 * 1024


async def get_video_metadata(session: aiohttp.ClientSession, url):
    async with session.get(url) as r:
        s = await r.text()

        p = next(re.finditer(ID_REGEX, s), None)
        video_id = p.group(1)

        p = next(re.finditer(TITLE_REGEX, s), None)
        title = p.group(1)

        p = next(re.finditer(URL_REGEX, s), None)
        v_url = HOST + p.group(0)

    async with session.get(v_url, headers={'Referer': url}, allow_redirects=False) as r:
        v_url = 'http:' + r.headers['Location']

    return title, v_url


async def download(session, url, path):
    title, url = await get_video_metadata(session, url)
    ext = next(re.finditer(r"\d+(\.\w+)\?", url)).group(1)
    target = path + title + ext

    timeout = aiohttp.ClientTimeout(total=20*60)
    async with session.get(url, timeout=timeout) as r:
        size = int(r.headers.get('content-length', 0))
        progressbar = tqdm(desc=title, total=size,
                           unit='B', unit_scale=True)

        with open(target, 'wb') as f:
            while True:
                chunk = await r.content.read(CHUNK_SIZE)
                if not chunk:
                    break
                f.write(chunk)
                progressbar.update(len(chunk))


async def main(loop):
    parser = argparse.ArgumentParser(description='Video Downloader')
    req_args = parser.add_argument_group('required arguments')

    parser.add_argument('--parallel', nargs='?', const=DEFAULT_PARALLEL, type=int,
                        help='Count of files can be downloading simultaneously. Default, %s' % DEFAULT_PARALLEL)
    req_args.add_argument('path', metavar='path', help='Target directory')
    req_args.add_argument('-U', '--url', action='append',
                          help='Page URL of video', required=True)
    args = parser.parse_args()

    path = args.path
    if path[-1] != '/':
        path += '/'

    headers = {
        'User-Agent': USER_AGENT,
    }

    async with aiohttp.ClientSession(loop=loop, headers=headers) as session:
        tasks = set()
        # When `load` flag not presented, use sync load
        tasks_limit = args.parallel or 1

        for url in args.url:
            if len(tasks) >= tasks_limit:
                done, tasks = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            tasks.add(loop.create_task(download(session, url, path)))

        await asyncio.wait(tasks)

if __name__ == "__main__":
    with closing(asyncio.get_event_loop()) as loop:
        loop.run_until_complete(main(loop))
