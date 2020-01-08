# Sibnet Downloader

Script for downloading videos from `video.sibnet.ru`

**Requires:**

- Python 3.6 or higher
- [aiohttp](https://github.com/aio-libs/aiohttp)
- [tqdm](https://github.com/tqdm/tqdm)

## Usage
```bash
python main.py -U https://video.sibnet.ru/video138... -U https://video.sibnet.ru/video140... /path/to/target/dir
```

### Command Line Arguments
<pre>
optional arguments:
  -h, --help            show this help message and exit

required arguments:
  path                  Target directory
  -U URL, --url URL     Page URL of video
</pre>

## Changelog (dev - delete before commit)
  - Вынес создание сессии наверх. Теперь все файлы загружаются в рамках одной и той же
    - У сессий нет таймаута, поэтому почему бы и нет?
    - [ ] Проверить есть ли разница в скоросте загрузки между ветками master и dev

## TODO
- [ ] Catch exception on errors in threads
- [ ] Preload info about next videos
- [ ] Graceful download exit (question on stop + delete file + continue with next video)
- [ ] Playlist download