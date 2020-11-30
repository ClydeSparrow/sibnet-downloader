import asyncio
from typing import List
from urllib.parse import urlparse

import aiohttp
import click

from common import Loader, VideoFile
from sibnet import SibnetLoader, SibnetVideo
from sovetromantica import SovetRomanticaLoader, SovetRomanticaVideo
from utils import coroutine


async def prepare_all_videos(loader: Loader, videos: List[VideoFile]):
    for video in videos:
        await loader.prepare(video)


async def proceed_all_videos(loader: Loader, videos: List[VideoFile]):
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
    # Validation
    hosts = set([urlparse(u).hostname for u in url])
    if len(hosts) > 1:
        raise Exception('Downloading videos from multiple hosts is not supported. '
                        'Please divide your list for multiple calls')
    if not hosts.issubset([SibnetLoader.HOST, SovetRomanticaLoader.HOST]):
        raise Exception(f"Unsupported host {hosts.pop()} is found")

    loader = None
    videos = []
    for video_url in url:
        if SibnetLoader.HOST in video_url:
            videos.append(SibnetVideo(page_url=video_url))
        if SovetRomanticaLoader.HOST in video_url:
            videos.append(SovetRomanticaVideo(page_url=video_url))

    session = aiohttp.ClientSession()
    if isinstance(videos[0], SibnetVideo):
        loader = SibnetLoader(session=session, save_to=path)
    if isinstance(videos[0], SovetRomanticaVideo):
        loader = SovetRomanticaLoader(session=session, save_to=path)

    await asyncio.wait([
        prepare_all_videos(loader, videos),
        proceed_all_videos(loader, videos),
    ])
    await session.close()


if __name__ == '__main__':
    main()
