import argparse
import asyncio
import os
import re
from contextlib import closing
from typing import Union

import aiohttp
from tqdm import tqdm

HOST = "https://video.sibnet.ru"
UA = "Mozilla/5.0 (Linux; Android 7.1.2; AFTMM Build/NS6265; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/70.0.3538.110 Mobile Safari/537.36"

CHUNK_SIZE = 64 * 1024  # Max(!) chunk size - 64 KB
DEFAULT_PARALLEL = 4
TIMEOUT = 20 * 60


def sink(path, size):
    """Writes data from download generators to file with
    tracking of process using progressbar

    Arguments:
        path {str} -- Path to file to write the download stream
        size {int} -- Size of video file
    """
    title = path.split('/')[-1]
    pb = tqdm(desc=title, total=size, unit='B', unit_scale=True)

    with open(path, 'r+b') as f:
        while True:
            chunk: tuple = yield
            if not chunk:
                break

            f.seek(chunk[0], os.SEEK_SET)
            f.write(chunk[1])
            pb.update(len(chunk[1]))

    pb.close()


class SibnetLoader:

    TITLE_REGEX = r"videoName\'>(.*)<\/h1>"
    URL_REGEX = r"\/v\/.+\d+.mp4"
    EXT_REGEX = r"\d+(\.\w+)\?"

    def __init__(self, url, session: Union[None, aiohttp.ClientSession] = None):
        self._session = session
        if session is None:
            self._session = aiohttp.ClientSession()

        self._player_url = url  # URL where video player is located
        self._file_url = None
        self._size = None

        self._title = None
        self._ext = None

    async def get_video_info(self):
        """Gets video's title, size and other information
        """
        async with self._session.get(self._player_url) as r:
            s = await r.text()

            p = next(re.finditer(self.TITLE_REGEX, s), None)
            self._title = p.group(1)

            p = next(re.finditer(self.URL_REGEX, s), None)
            self._file_url = HOST + p.group(0)

        # Redirect to final video URL & update loader fields
        await self.get_video_size()
        self._ext = next(re.finditer(self.EXT_REGEX, self._file_url)).group(1)

    async def get_video_size(self) -> int:
        """Redirects to final video's location and returns size from Content-Length

        Returns:
            int -- Video file size
        """
        url = self._file_url
        while self._size is None:
            async with self._session.head(url, headers={'Referer': self._player_url}) as r:
                if r.status == 200:
                    self._file_url = url
                    self._size = int(r.headers['Content-Length'])
                elif r.status == 302:
                    url = r.headers.get('Location')
                    if url.startswith('//'):
                        url = 'http:' + url
                else:
                    r.raise_for_status()
        return self._size

    async def _download_part(self, start, end, sink):
        i = start
        async with self._session.get(self._file_url, headers={'Range': f'bytes={start}-{end}'}, timeout=TIMEOUT) as r:
            while True:
                chunk = await r.content.read(CHUNK_SIZE)
                if not chunk:
                    break

                sink.send((i, chunk))
                i += len(chunk)

        return i - start

    async def download(self, path):
        download_futures = []
        fsink = sink(os.path.join(path, self.filepath), self._size)
        next(fsink)  # Starting generator. After next() we can send values

        p_size = self._size // DEFAULT_PARALLEL
        for i in range(DEFAULT_PARALLEL):
            start = i * p_size
            end = (i+1) * p_size - 1
            if i == DEFAULT_PARALLEL - 1:
                end = ''

            download_futures.append(
                self._download_part(start, end, sink=fsink))

        for download_future in asyncio.as_completed(download_futures):
            await download_future

        return True

    def create_file(self, path):
        if self.size is None:
            raise Exception("File size is unknown. Do get_video_info() first")

        disk = os.statvfs(path)
        if self._size > disk.f_bavail * disk.f_frsize:
            raise Exception(
                f"Not enough space on disk for file. {self._size // 2**10} KB required")

        with open(os.path.join(path, self.filepath), 'w+b') as f:
            f.seek(self._size-1)
            f.write(b'\0')

    @property
    def title(self) -> Union[None, str]:
        return self._title

    @property
    def fileurl(self) -> Union[None, str]:
        return self._file_url

    @property
    def filepath(self) -> str:
        return self._title.replace('/', ' - ') + self._ext

    @property
    def size(self) -> Union[None, int]:
        return self._size


async def proceed_video(loader: SibnetLoader, path) -> bool:
    """Downloads video and saves file at specified path

    Arguments:
        loader {SibnetLoader} -- prepared loader with initialized URL
        path {srt} -- Destination where file will be written
    """
    await loader.get_video_info()
    loader.create_file(path)

    result = await loader.download(path)
    return result


def init() -> argparse.Namespace:
    """Parses console args on script start"""
    parser = argparse.ArgumentParser(description='Video Downloader')
    parser.add_argument('path', metavar='path', help='Target directory')
    parser.add_argument('-U', '--url', action='append',
                        help='Page URL of video', required=True)
    return parser.parse_args()


async def main():
    args = init()

    async with aiohttp.ClientSession(headers={'User-Agent': UA}) as session:
        for url in args.url:
            # TODO: Create tasks for each url to gather video's details
            loader = SibnetLoader(url, session)
            await proceed_video(loader, path=args.path)

if __name__ == "__main__":
    with closing(asyncio.get_event_loop()) as loop:
        loop.run_until_complete(main())
