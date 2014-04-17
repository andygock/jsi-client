# justseed.it cli client

Command line client for [justseed.it](https://justseed.it) seedbox service.

### Features

- Batch add .torrent files, and set maximum ratio at the same time
- Add torrents by magnet link
- Start and stop torrents
- Change torrent name or maximum ratio
- Display download links
- Generate aria2 script
- Supports requesting and reading gzip compressed data from server
- Colored console output
- Works in Windows, Linux and Mac OSX

## Installation

This is designed and tested on [Python 2.7](http://www.python.org/download/), you'll probably need this version to run this script (exception being if you are downloading a Windows pre-compiled binary of this program). I haven't tested it on other versions.

### Using source

To run, it requires the installation of the following packages (which are in addition to those standard packages which come with Python):

- [poster](http://pypi.python.org/pypi/poster/)
- [bencode](http://pypi.python.org/pypi/bencode/)
- [colorama](https://pypi.python.org/pypi/colorama)

They can be easily installed using `pip`:

	pip install poster bencode colorama

Windows users can use [pip-Win](https://sites.google.com/site/pydatalog/python/pip-for-windows) which makes it very easy to install python packages.

### Using Windows compiled binary

Coming soon.

### Setting up PATH

To use `jsi.py` on the command line, without having to type the full path, the installed path must be in your system path environment variable.

### Set up API key

You'll need an API key for use with your justseed.it account. You can generate one in your options page at the justseed.it site. Create a plain text file called `.justseedit_apikey` in the root of your home directory with the API key in the file.

If this file is not found in your home directory, then the script will look for it in the same directory as the running jsi.py file. If it is not found in either, it will display an error and quit.

All the above can be overwritten, and a api key can be specified on the command line using the `--api-key` option, however it is not recommended to use this method as there may be security implications for doing this.

#### Where is my home directory?

If you're not sure where your home directory on your computer, run the following to find out:

	python -c "import os; print os.path.expanduser('~')"

### Set up default options

There easiest way is to set these up, is to use environment variables:

- `JSI_OUTPUT_DIR` will set the default output directory, for use with aria2 script output. Use a trailing `/` slash.
- `JSI_RATIO` will set the default ratio used when adding new torrents
- `JSI_ARIA2_OPTIONS` will set detfault options for aria2 script. Currently this is `--file-allocation=none --check-certificate=false --max-concurrent-downloads=8 --continue --max-connection-per-server=8 --min-split-size=1M`

If none of the above are found, then the defaults set in `jsi.py` will be used. Theis is found near the top of the `JustSeedIt` class definition.

## Show usage options

For help:

	jsi.py -h
	
## Examples of usage

Add a single torrent file with maximum ratio of 2.0

	jsi.py -r 2.0 -t FILE
	
List current torrents in system:

	jsi.py --list

List only incomplete torrents in system:

	jsi.py --list-incomplete

Add multiple 3 torrent files at the same time, with default ratio:

	jsi.py -t FILE1 FILE2 FILE3

Add all .torrent files from current directory and set a maximum ratio of 1.0 for each one:

	jsi.py -r 1.0 -t *.torrent
	
View download links for torrent with ID #5:

	jsi.py --download-links 5

Save download links for torrent with ID #5 and #7 to file `links.txt`:

	jsi.py --download-links 5 7 > links.txt
	
Generate [aria2](http://aria2.sourceforge.net/) download links for torrent with ID #5 and #7, and save to file `aria2-script`:

	jsi.py --aria2 5 7 > aria2-script
	
And then view and run the aria2-script commands (for Linux and Mac):

	cat aria2-script
	sh aria2-script
	
For Windows users, you may want to create a batch file instead:

	jsi.py --aria2 5 7 > aria2-script.bat
	
Now check the contents, and run it:

	type aria2-script.bat
	aria2-script.bat
	
Change maximum ratio of torrent #13 to 2.5:

	jsi.py -r 2.5 -e 13
	
Change maximum ratio of torrent #1, #2 and #3 to 2.5, and show debugging info:
	
	jsi.py --debug --ratio 2.5 --edit 1 2 3
	
We can use `A..B` format as shorthand to describe a range of integers from A to B. For example, to change maximum ratio of torrent #0 to #10 inclusive, and #15 to 1.0:

	jsi.py --ratio 1.0 --edit 0..10 15
	
Start or resume torrent #5, #6 and #7:

	jsi.py --start 5..7

Stop torrent #14 and #17:

	jsi.py --stop 14 17
	
# LICENSE
	
	Copyright (c) 2014, Andy Gock. All rights reserved.

	Redistribution and use in source and binary forms, with or without
	modification, are permitted provided that the following conditions are
	met:

	1. Redistributions of source code must retain the above copyright
	notice, this list of conditions and the following disclaimer.

	2. Redistributions in binary form must reproduce the above copyright
	notice, this list of conditions and the following disclaimer in the
	documentation and/or other materials provided with the distribution.

	3. Neither the name of the copyright holder nor the names of its
	contributors may be used to endorse or promote products derived from
	this software without specific prior written permission.

	THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
	"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
	LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
	A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
	HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
	SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
	LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
	DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
	THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
	(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
	OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.	