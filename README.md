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

## TODO
- [ ] Add tests
- [ ] Gather info from all video URLs right after start & make a list of progressbars
- [ ] Graceful download exit (question on stop + delete file + continue with next video)
- [ ] Playlist download