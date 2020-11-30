import asyncio
import os
import re

from tqdm import tqdm

import settings
from common import VideoFile, Loader

UA = "Mozilla/5.0 (Linux; Android 7.1.2; AFTMM Build/NS6265; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/70.0.3538.110 Mobile Safari/537.36"


class SibnetVideo(VideoFile):
    @property
    def ext(self):
        return next(re.finditer(SibnetLoader.EXT_REGEX, self.file_url)).group(1)


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


class SibnetLoader(Loader):

    HOST = 'video.sibnet.ru'
    HEADERS = {'User-Agent': UA}

    TITLE_REGEX = r"videoName\'>(.*)<\/h1>"
    URL_REGEX = r"\/v\/.+\d+.mp4"
    EXT_REGEX = r"\d+(\.\w+)\?"

    async def prepare(self, videofile: VideoFile):
        """Enrich VideoFile object with data parsed from video page"""
        # Parse title and link to video from page
        async with self._session.get(videofile.page_url) as r:
            s = await r.text()

            p = next(re.finditer(self.TITLE_REGEX, s), None)
            videofile.title = p.group(1)

            p = next(re.finditer(self.URL_REGEX, s), None)
            videofile.file_url = self.HOST + p.group(0)

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
