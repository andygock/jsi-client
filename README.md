# justseedit cli client

Command line client for [justseed.it](https://justseed.it) seedbox service.

## Installation

### Using source

To run, it requires the the following packages which are in addition to those standard packages which come with Python.:

- [xmltodict](http://pypi.python.org/pypi/xmltodict/)
- [poster](http://pypi.python.org/pypi/poster/)
- [bencode](http://pypi.python.org/pypi/bencode/)

They can be easily installed using `pip`. Example `pip install xmltodict` to install xmltodict.

Windows users can use [pip-Win](https://sites.google.com/site/pydatalog/python/pip-for-windows) which makes it very easy to install python packages

### Using Windows compiled binary

Coming soon

### Setting up PATH

To use jsi.py on the command line, without having to type the full path to jsi.py, the installed path must be in your system path environment variable.

## Set up API key

You'll need an API key for use with your justseed.it account. Create a file called `.justseedit_apikey` in your home directory. If this file is not found in your home directory, then it will look for it in the same directory as the running jsi.py. If it is not found in either, it will display an error and quit.

All the above can be overwritten, and a api key can be specified on the command line using the `--api-key` option. It is not recommended to use this method.

## Show usage options

For help:

	jsi.py -h
	
## Examples of usage

Add a single torrent file with maximum ratio of 2.0

	jsi.py -r 2.0 -t FILE
	
Check current torrents in system:

	jsi.py --list
	
Add multiple 3 torrent files at the same time, with default ratio:

	jsi.py -t FILE1 FILE2 FILE3
	
Add all .torrent files from current directory with maximum ratio of 1.0

	jsi.py -r 1.0 -t *.torrent
	
View download links for torrent with ID number 5:

	jsi.py --download-links 5

Save download links for torrent with ID number 5 to file `links.txt`:

	jsi.py --download-links 5 > links.txt
	
Generate [aria2](http://aria2.sourceforge.net/) download links for torrent with ID 5 and save to file `aria2-script`

	jsi.py --aria2 5 > aria2-script
	
And then view and run the aria2-script commands:

	cat aria2-script
	sh aria2-script
	
Change maximum ratio of torrent #13 to 2.5:

	jsi.py -r 2.5 -e 13
	
Change maximum ratio of torrent #1, #2 and #3 to 2.5, and show debugging info:
	
	jsi.py --debug --ratio 2.5 --edit 1 2 3
	
Change maximum ratio of torrent #1 to #10 inclusive, and #15 to 1.0 (not suitable for windows console):

	jsi.py --ratio 1.0 --edit {0..10} 15
	
