import asyncio
import aiohttp
import argparse
import re
import os

from contextlib import closing
from typing import Union
from tqdm import tqdm


HOST = "https://video.sibnet.ru"
USER_AGENT = "Mozilla/5.0 (Linux; Android 7.1.2; AFTMM Build/NS6265; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/70.0.3538.110 Mobile Safari/537.36"

CHUNK_SIZE = 64 * 1024  # Max(!) chunk size - 64 KB
DEFAULT_PARALLEL = 4


def coroutine(func):
    def start(*args, **kwargs):
        cr = func(*args, **kwargs)
        next(cr)
        return cr
    return start


@coroutine
def sink(path, size):
    title = path.split('/')[-1]
    progressbar = tqdm(desc=title, total=size, unit='B', unit_scale=True)

    with open(path, 'r+b') as f:
        while True:
            chunk: tuple = yield
            if not chunk:
                break

            f.seek(chunk[0], os.SEEK_SET)
            f.write(chunk[1])
            progressbar.update(len(chunk[1]))


class SibnetLoader:

    ID_REGEX = r".*\.php\?videoid=([0-9]*)"
    TITLE_REGEX = r"videoName\'>(.*)<\/h1>"
    URL_REGEX = r"\/v\/.+\d+.mp4"
    EXT_REGEX = r"\d+(\.\w+)\?"

    def __init__(self, url, session: Union[None, aiohttp.ClientSession] = None):
        self._session = session
        if session is None:
            self._session = aiohttp.ClientSession()

        self._url = url
        self._title = ''
        self._fileurl = ''
        self._size = -1

    def __str__(self):
        return f"SibnetLoader(title={self._title}, fileurl={self._fileurl}, size={self._size})"

    async def get_video_info(self):
        async with self._session.get(self._url) as r:
            s = await r.text()

            # p = next(re.finditer(self.ID_REGEX, s), None)
            # video_id = p.group(1)

            p = next(re.finditer(self.TITLE_REGEX, s), None)
            self._title = p.group(1)

            p = next(re.finditer(self.URL_REGEX, s), None)
            url = HOST + p.group(0)

        headers = await self.get_video_headers(url)
        self._size = int(headers['Content-Length'])

        ext = next(re.finditer(r"\d+(\.\w+)\?", self._fileurl)).group(1)
        self._title += ext

        return self._title, self._size

    async def get_video_headers(self, url) -> dict:
        while True:
            async with self._session.head(url, headers={'Referer': self._url}) as r:
                if r.status == 200:
                    self._fileurl = url
                    return r.headers
                elif r.status == 302:
                    url = r.headers.get('Location')
                    if url.startswith('//'):
                        url = 'http:' + url
                else:
                    r.raise_for_status()

    async def _download_part(self, start, end, sink):
        i = start
        async with self._session.get(self._fileurl, headers={'Range': f'bytes={start}-{end}'}) as r:
            while True:
                chunk = await r.content.read(CHUNK_SIZE)
                if not chunk:
                    break

                sink.send((i, chunk))
                i += len(chunk)

        return i - start

    @asyncio.coroutine
    def download(self, path):
        download_futures = []
        fsink = sink(path, self._size)

        p_size = self._size // DEFAULT_PARALLEL
        for i in range(DEFAULT_PARALLEL):
            start = i * p_size
            end = (i+1) * p_size - 1
            if i == DEFAULT_PARALLEL - 1:
                end = ''

            download_futures.append(
                self._download_part(start, end, sink=fsink))

        for download_future in asyncio.as_completed(download_futures):
            result = yield from download_future

        return True

    def close(self):
        self._session = None


def check_diskspace(size: int):
    """Checks if there is enough space on disk to create file

    Arguments:
        size {int} -- file size to create
    """
    disk = os.statvfs('/')
    if size > disk.f_bavail * disk.f_frsize:
        return False
    return True


async def proceed_video(loop, url, path):
    headers = {'User-Agent': USER_AGENT}
    async with aiohttp.ClientSession(loop=loop, headers=headers) as session:
        loader = SibnetLoader(url, session)
        title, size = await loader.get_video_info()
        # print(loader)

        if not check_diskspace(size):
            raise Exception(
                f"Not enough space on disk. {size // 2**10} KB required")

        # Allocate disk space. It is necessary
        # because file is not written sequentially
        with open(path + '/' + title, 'w+b') as f:
            f.seek(size-1)
            f.write(b'\0')

        # if 'Accept-Ranges' not in v_headers:
        #     pass

        result = await loader.download(path + '/' + title)

        loader.close()


def init() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Video Downloader')
    parser.add_argument('path', metavar='path', help='Target directory')
    parser.add_argument('-U', '--url', action='append',
                        help='Page URL of video', required=True)
    return parser.parse_args()


async def main(loop):
    args = init()

    for url in args.url:
        result = await proceed_video(loop, url, path=args.path)
        print('finished:', url)

if __name__ == "__main__":
    with closing(asyncio.get_event_loop()) as loop:
        loop.run_until_complete(main(loop))
