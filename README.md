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

## Set up API key

You'll need an API key for use with your justseed.it account. Create a file called `.justseedit_api_key` in the same directory as `jsi.py` or in your home directory with the API key inside.

For help:

	jsi.py -h
	
## Examples of usage

Add a single torrent file with maximum ratio of 2.0

	wget http://cdimage.debian.org/debian-cd/7.4.0/amd64/bt-cd/debian-7.4.0-amd64-netinst.iso.torrent
	jsi.py -r 2.0 -t debian-7.4.0-amd64-netinst.iso.torrent
	
Check current torrents in system:

	jsi.py --list
	
Add multiple 3 torrent files at the same time, with default ratio:

	jsi.py -t debian-7.4.0-amd64-CD-1.iso.torrent debian-7.4.0-amd64-CD-2.iso.torrent debian-7.4.0-amd64-CD-3.iso.torrent
	
Add all .torrent files from current directory with maximum ratio of 1.0

	jsi.py -r 1.0 -t *.torrent
	
View download links for torrent with ID number 5:

	jsi.py --download-links 5

Save download links for torrent with ID number 5 to file `links.txt`:

	jsi.py --download-links 5 > links.txt
	
Generate aria2 download links for torrent with ID 5 and save to file `aria2-script`

	jsi.py --aria2 5 > aria2-script
	
(and view, then run the aria2-script)

	cat aria2-script
	sh aria2-script
	
	