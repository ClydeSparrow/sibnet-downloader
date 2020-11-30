import os
import re
import subprocess
import sys
from collections import OrderedDict
from urllib.parse import urljoin, urlparse

from tqdm import tqdm

from common import VideoFile, Loader


def filesizeMiB(filename):
    s = os.stat(filename)
    return s.st_size / 1024 / 1024.0


class SovetRomanticaVideo(VideoFile):
    # TODO: unite page_url and file_url
    def __init__(self, page_url=None):
        super().__init__(page_url)
        # Custom attributes
        self.fragments = []

    @property
    def ext(self):
        return '.mp4'


class SovetRomanticaLoader(Loader):

    HOST = 'sovetromantica.com'
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/72.0.3626.119 Safari/537.36',
        'Origin': 'https://sovetromantica.com',
    }

    TITLE_REGEX = r'<div class="block--full anime-name"><div.+?>(.+?) \/ (.+?) <\/div>'
    URL_REGEX = r'<meta property="ya:ovs:content_url" content="(.+?)"'

    def __init__(self, save_to='.', session=None, tempdir='/tmp/'):
        super().__init__(save_to, session)

        self.tempdir = tempdir  # TODO: check temp dir for existance
        self.media_playlist = None  # TODO: try in-memmory first
        self.fragments = OrderedDict()  # TODO: prove that OrderedDict is required

    async def prepare(self, video: SovetRomanticaVideo):
        s = await self.get_page(video.page_url)

        # Fetch original title (goes after "/")
        p = next(re.finditer(self.TITLE_REGEX, s), None)
        video.title = p.group(2).strip()

        # Fetch master playlist link
        p = next(re.finditer(self.URL_REGEX, s), None)
        master_playlist = p.group(1)

        video.fragments, video.playlist_file = await self.process_master_playlist(master_playlist)
        video.prepared = True

    async def get_page(self, url):
        async with self._session.get(url) as r:
            return await r.text()

    async def process_master_playlist(self, url):
        """Chooses playlist with best resolution and process it"""
        s = await self.get_page(url)

        target_playlist = None
        highest_resolution = 0
        target_on_next_line = False
        res_pattern = re.compile(r'RESOLUTION=(\d+)x(\d+)')
        for line in s.splitlines():
            contains_res = res_pattern.search(line)
            if contains_res:
                width, height = contains_res.group(1), contains_res.group(2)
                if int(height) > highest_resolution:
                    highest_resolution = int(height)
                    target_on_next_line = True
            if line.startswith('#'):
                continue
            if target_on_next_line:
                target_playlist = line
                target_on_next_line = False
            if not target_playlist:
                target_playlist = line
        return await self.process_media_playlist(urljoin(url, target_playlist))

    async def process_media_playlist(self, url):
        """Returns list of fragment URLs saving it in temporary folder"""
        s = await self.get_page(url)

        playlist_file = os.path.join(self.tempdir, url.split('/')[-1])
        with open(playlist_file, 'w') as f:
            f.write(s)

        fragments = []
        for line in s.split('\n'):
            if line.startswith('#') or not line.strip():
                continue
            if line.endswith(".m3u8"):
                raise RuntimeError("Media playlist should not include .m3u8")
            fragments.append(urljoin(url, line))
        return fragments, playlist_file

    async def proceed_video(self, video: SovetRomanticaVideo):
        await self.download(video)
        # After playlist is downloaded, call `ffmpeg`
        # TODO: clean up fragments once process is finished

    async def _download_fragment(self, url):
        # Download single fragment in TEMP folder
        pass

    async def download(self, video: SovetRomanticaVideo):
        # TODO: Limit async processes - ???
        # TODO: Can be mapped to something real and understandable
        for fragment in tqdm(video.fragments, desc=video.title, unit='pieces'):
            # TODO: Support of already downloaded files
            filename = urlparse(fragment).path.split('/')[-1]
            local_path = os.path.join(self.tempdir, filename)

            async with self._session.get(fragment) as r:
                s = await r.content.read()

            with open(local_path, 'w+b') as f:
                f.write(s)

            self.fragments[fragment] = local_path

        target = os.path.join(self._filepath, video.filename)
        cmd = ["ffmpeg",
               "-loglevel", "warning",
               "-allowed_extensions", "ALL",
               "-i", os.path.join(self.tempdir, video.playlist_file),
               "-acodec", "copy",
               "-vcodec", "copy",
               "-bsf:a", "aac_adtstoasc",
               target]

        print(f"Running: {cmd}")
        proc = subprocess.run(cmd)
        if proc.returncode != 0:
            print(f"run ffmpeg command failed: exitcode={proc.returncode}")
            sys.exit(proc.returncode)
        print(f"mp4 file created, size={filesizeMiB(target)}MiB, filename={target}")

        # print("Removing temp files in dir: \"%s\"", self.tempdir)
        # if os.path.exists("/bin/rm"):
        #     subprocess.run(["/bin/rm", "-rf", self.tempdir])
