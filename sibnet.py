import asyncio
import os
import re

from typing import Union

import aiohttp
import click

from tqdm import tqdm

import settings

from utils import coroutine


def file_sink(path, size, **kwargs):
    """Writes data from download generators to file with
    tracking of process using progressbar

    Arguments:
        path {str} -- Path to file to write the download stream
        size {int} -- Size of video file
    """
    title = path.split('/')[-1]
    pbar = tqdm(desc=title, total=size, unit='B', unit_scale=True)

    with open(path, 'r+b') as f:
        while True:
            chunk = yield
            if not chunk:
                break

            f.seek(chunk[0], os.SEEK_SET)
            f.write(chunk[1])
            pbar.update(len(chunk[1]))

    pbar.close()


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
        """Get video title, size and other information"""
        async with self._session.get(self._player_url) as r:
            s = await r.text()

            p = next(re.finditer(self.TITLE_REGEX, s), None)
            self._title = p.group(1)

            p = next(re.finditer(self.URL_REGEX, s), None)
            self._file_url = settings.HOST + p.group(0)

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
        async with self._session.get(self._file_url, headers={'Range': f'bytes={start}-{end}'}, timeout=settings.TIMEOUT) as r:
            while True:
                chunk = await r.content.read(settings.MAX_CHUNK_SIZE)
                if not chunk:
                    break

                sink.send((i, chunk))
                i += len(chunk)

        return i - start

    async def download(self, path):
        download_futures = []
        fsink = file_sink(path=os.path.join(path, self.filepath), size=self._size)
        next(fsink)  # Starting generator. After next() we can send values

        p_size = self._size // settings.HANDLERS
        for i in range(settings.HANDLERS):
            start = i * p_size
            end = min(self.size, (i+1) * p_size - 1)

            download_futures.append(self._download_part(start, end, sink=fsink))

        for download_future in asyncio.as_completed(download_futures):
            await download_future

        return True

    def create_file(self, path):
        if self.size is None:
            raise Exception("File size is unknown. Do get_video_info() first")

        disk = os.statvfs(path)
        if self._size > disk.f_bavail * disk.f_frsize:
            raise MemoryError(
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


async def proceed_video(loader: SibnetLoader, path):
    """Downloads video and saves file at specified path

    Arguments:
        loader {SibnetLoader} -- prepared loader with initialized URL
        path {srt} -- Destination where file will be written
    """
    try:
        loader.create_file(path)
        await loader.download(path)
    except MemoryError as e:
        print(str(e))
    except Exception as e:
        os.remove(os.path.join(path, loader.filepath))
        print(f"{e}. File was deleted")


@click.command()
@click.option('-U', '--url', multiple=True, help='Page URL of video')
@click.argument('path', type=click.Path(exists=True))
@coroutine
async def main(url, path):
    """Script to download videos from video.sibnet.ru"""
    async with aiohttp.ClientSession(headers={'User-Agent': settings.UA}) as session:
        loaders = [SibnetLoader(url, session) for url in url]

        await loaders[0].get_video_info()

        for loader, next_loader in zip(loaders, loaders[1:]):
            await asyncio.wait([
                proceed_video(loader, path=path),
                next_loader.get_video_info()
            ])

        await proceed_video(loaders[-1], path=path)


if __name__ == '__main__':
    main()
