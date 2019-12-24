import unittest
import asyncio
import aiohttp

from contextlib import closing

from sibnet import SibnetLoader, UA

URL_1 = "https://video.sibnet.ru/video2057122?utm_source=player&utm_medium=video&utm_campaign=EMBED"
TITLE_1 = "K-ON!! - Special 01 (субтитры).mp4"
SIZE_1 = 10923870

URL_2 = "https://video.sibnet.ru/video1618755-Belaya_korobka_Shirobako__6___subtitryi_/"
TITLE_2 = "Белая коробка/Shirobako (6) (субтитры).mp4"

_DIR = '/tmp/'

def async_test(f):
    def wrapper(*args, **kwargs):
        coro = asyncio.coroutine(f)
        future = coro(*args, **kwargs)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(future)
    return wrapper

class TestLoader(unittest.TestCase):

    # def __init__(self, *args, **kwargs):
    #     super().__init__(*args, **kwargs)

    # def setUp(self):
    #     self.loop = asyncio.get_event_loop()
    #     self.session = aiohttp.ClientSession()

    # def tearDown(self):
    #     self.session.close()
    #     self.loop.close()

    @async_test
    async def test_create_file_with_special_chars(self):
        async with aiohttp.ClientSession(headers={'User-Agent': UA}) as session:
            l = SibnetLoader(URL_2, session=session)
            l._title = TITLE_2
            l._size = 1

            l.create_file(_DIR)
            # Check that video title in class haven't changed
            self.assertEqual(l.title, TITLE_2)

    # @async_test
    # def test_video_size(self):
    #     l = SibnetLoader(URL_1)
    #     l._file_url = "https://video.sibnet.ru/v/2ced5772fc1eaec0745d32e85df60668/2057122.mp4"
    #     size = yield from l.get_video_size()

    #     self.assertEqual(size, SIZE_1)
    #     yield from l._session.close()

    # @async_test
    # def test_video_info(self):
    #     l = SibnetLoader(URL_1)
    #     yield from l.get_video_info()

    #     self.assertEqual(l.title, TITLE_1)
    #     self.assertEqual(l.size, SIZE_1)

    #     yield from l._session.close()

    # @async_test
    # def test_loader_init_without_session(self):
    #     # with closing(asyncio.get_event_loop()) as loop:
    #     l = SibnetLoader("aaa")
    #     self.assertIsNone(l.title)
    #     yield from l._session.close()


if __name__ == '__main__':
    unittest.main()
