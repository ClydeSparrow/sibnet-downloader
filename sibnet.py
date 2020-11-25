import asyncio
import json
import os
import re
from typing import List

import aiohttp
import click
from tqdm import tqdm

import settings
from utils import coroutine


class VideoFile:
    __slots__ = ['page_url', 'file_url', 'title', 'size', 'prepared']

    def __init__(self, page_url=None):
        self.page_url = page_url
        self.file_url = None
        self.title = None
        self.size = None
        self.prepared = False

    def __repr__(self):
        return json.dumps(self.__dict__, indent=4)

    @property
    def ext(self):
        return next(re.finditer(SibnetLoader.EXT_REGEX, self.file_url)).group(1)

    @property
    def filename(self):
        return self.title + self.ext


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

    def __init__(self, save_to='.', session=None):
        self._session = session or aiohttp.ClientSession()
        self._filepath = save_to

    async def prepare(self, videofile: VideoFile):
        """Enrich VideoFile object with data parsed from video page"""
        # Parse title and link to video from page
        async with self._session.get(videofile.page_url) as r:
            s = await r.text()

            p = next(re.finditer(self.TITLE_REGEX, s), None)
            videofile.title = p.group(1)

            p = next(re.finditer(self.URL_REGEX, s), None)
            videofile.file_url = settings.HOST + p.group(0)

        # Redirect to final video URL
        url = videofile.file_url
        while videofile.size is None:
            async with self._session.head(url, headers={'Referer': videofile.page_url}) as r:
                if r.status == 200:
                    videofile.file_url = url
                    videofile.size = int(r.headers['Content-Length'])
                elif r.status == 302:
                    url = r.headers.get('Location')
                    if url.startswith('//'):
                        url = 'http:' + url
                else:
                    r.raise_for_status()

        videofile.prepared = True
        return videofile.size

    async def proceed_video(self, video):
        """Downloads video and saves file at specified path"""
        try:
            self.create_file(video.filename, video.size)
            await self.download(video)
        except MemoryError as e:
            print(f'"{video.title}" can\'t be proceeded: {e}')
        except Exception as e:
            os.remove(os.path.join(self._filepath, video.filename))
            print(f"{e}. File was deleted")

    async def _download_part(self, url, start, end, sink):
        i = start
        async with self._session.get(url, headers={'Range': f'bytes={start}-{end}'}, timeout=settings.TIMEOUT) as r:
            while True:
                chunk = await r.content.read(settings.MAX_CHUNK_SIZE)
                if not chunk:
                    break

                sink.send((i, chunk))
                i += len(chunk)

        return i - start

    async def download(self, video: VideoFile):
        download_futures = []
        fsink = file_sink(path=os.path.join(self._filepath, video.filename), size=video.size)
        next(fsink)  # Starting generator. Only after next() it will accept values

        p_size = video.size // settings.HANDLERS
        for i in range(settings.HANDLERS):
            start = i * p_size
            end = min(video.size, (i+1) * p_size - 1)

            download_futures.append(self._download_part(video.file_url, start, end, sink=fsink))

        for download_future in asyncio.as_completed(download_futures):
            await download_future

        return True

    def create_file(self, filename, size):
        path = os.path.join(self._filepath, filename)

        disk = os.statvfs(self._filepath)
        if size > disk.f_bavail * disk.f_frsize:
            raise MemoryError(f"Not enough space on disk for file. {self // 2**10} KB required")

        with open(path, 'w+b') as f:
            f.seek(size-1)
            f.write(b'\0')


async def prepare_all_videos(loader: SibnetLoader, videos: List[VideoFile]):
    for video in videos:
        await loader.prepare(video)


async def proceed_all_videos(loader: SibnetLoader, videos: List[VideoFile]):
    for video in videos:
        # Wait until video's page is parsed
        while not video.prepared:
            await asyncio.sleep(.5)

        await loader.proceed_video(video)


@click.command()
@click.option('-U', '--url', multiple=True, help='Page URL of video')
@click.argument('path', type=click.Path(exists=True))
@coroutine
async def main(url, path):
    """Script to download videos from video.sibnet.ru"""
    videos = [VideoFile(page_url=url) for url in url]
    async with aiohttp.ClientSession(headers={'User-Agent': settings.UA}) as session:
        loader = SibnetLoader(session=session, save_to=path)

        await asyncio.wait([
            prepare_all_videos(loader, videos),
            proceed_all_videos(loader, videos),
        ])


if __name__ == '__main__':
    main()
