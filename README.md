# Sibnet Downloader

Script for downloading videos from `video.sibnet.ru`

**Requires:**

- Python 3.6 or higher
- argparse
- aiohttp

## Usage
```bash
python sibnet.py -U "https://video.sibnet.ru/video138..." -U "https://video.sibnet.ru/video140..." /path/to/target/dir
```

### Command Line Arguments
<pre>
optional arguments:
  -h, --help            show this help message and exit
  --parallel [PARALLEL]
                        Count of files can be downloading simultaneously. Default, 2

required arguments:
  path                  Target directory
  -U URL, --url URL     Page URL of video
</pre>