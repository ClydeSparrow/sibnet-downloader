import json

import aiohttp


class VideoFile:
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
        raise NotImplemented

    @property
    def filename(self):
        return self.title + self.ext


class Loader:
    HEADERS = {}

    def __init__(self, save_to='.', session=None):
        self._session = session or aiohttp.ClientSession()
        if self.HEADERS:
            self._session.headers.update(self.HEADERS)

        self._filepath = save_to

    async def prepare(self, videofile: VideoFile):
        raise NotImplemented

    async def proceed_video(self, video: VideoFile):
        raise NotImplemented

    async def download(self, video: VideoFile):
        raise NotImplemented
