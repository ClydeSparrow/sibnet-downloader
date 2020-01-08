import unittest
import os
import asyncio
import aiohttp

from contextlib import closing

from sibnet import SibnetLoader, UA

URL_1 = "https://video.sibnet.ru/video2057122?utm_source=player&utm_medium=video&utm_campaign=EMBED"
TITLE_1 = "K-ON!! - Special 01 (субтитры)"
SIZE_1 = 10923870

URL_2 = "https://video.sibnet.ru/video1618755-Belaya_korobka_Shirobako__6___subtitryi_/"
TITLE_2 = "Белая коробка/Shirobako (6) (субтитры)"

TMP_DIR = '/tmp/'

def async_test(f):
    def wrapper(*args, **kwargs):
        coro = asyncio.coroutine(f)
        future = coro(*args, **kwargs)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(future)
    return wrapper

class TestLoader(unittest.TestCase):

    @async_test
    def test_loader_init_without_session(self):
        l = SibnetLoader("aaa")
        self.assertIsNone(l.title)
        yield from l._session.close()

    @async_test
    async def test_create_file_with_special_chars(self):
        async with aiohttp.ClientSession(headers={'User-Agent': UA}) as session:
            l = SibnetLoader(URL_2, session=session)
            l._title, l._ext = TITLE_2, '.mp4'
            l._size = 2 ** 10

            l.create_file(TMP_DIR)
            # Check that video title in class haven't changed
            self.assertEqual(l.title, TITLE_2)

            p = os.path.join(TMP_DIR, l.filepath)
            # Check file exists & file size
            self.assertTrue(os.path.isfile(p))
            self.assertEqual(l.size, os.stat(p).st_size)
            # Delete file
            os.remove(p)

    @async_test
    async def test_video_details(self):
        async with aiohttp.ClientSession(headers={'User-Agent': UA}) as session:
            l = SibnetLoader(URL_1, session=session)
            # Before it was like `l._file_url = "..."`,
            # but file URLs at video.sibnet have TTL
            await l.get_video_info()

            self.assertEqual(l.size, SIZE_1)
            self.assertEqual(l.title, TITLE_1)

if __name__ == '__main__':
    unittest.main()
