# justseedit cli client

To run, it requires the the following packages:

- xmltodict
- poster

They're not usually installed with Python, but can be easily installed using `pip`.

For help:

	jsi.py -h
	
Dump of help options:

	usage: jsi.py [-h] [-m MAGNET-TEXT] [-t TORRENT-FILE] [-i INFOHASH] [-l]
				  [--download-links INFO-HASH] [-p] [-r RATIO] [-v] [-d] [--dry]
				  [--infomap] [--pieces INFO-HASH] [--bitfield INFO-HASH]
				  [--files INFO-HASH] [--trackers INFO-HASH] [--peers INFO-HASH]
				  [--start INFO-HASH] [--stop INFO-HASH] [--delete INFO-HASH]
				  [--aria2 INFO-HASH] [--aria2-options OPTIONS] [--xml]

	optional arguments:
	  -h, --help            show this help message and exit
	  -m MAGNET-TEXT, --magnet MAGNET-TEXT
							add torrent using magnet link
	  -t TORRENT-FILE, --torrent-file TORRENT-FILE
							add torrent with .torrent file
	  -i INFOHASH, --info INFOHASH
							show info for torrent (by infohash or ID)
	  -l, --list            list torrents
	  --download-links INFO-HASH
							get download links
	  -p, --pause           pause when finished
	  -r RATIO, --ratio RATIO
							set maximum ratio (used in conjunction with -t or -m)
	  -v, --verbose         verbose mode
	  -d, --debug           debug mode
	  --dry                 dry run
	  --infomap             show ID to infohash map
	  --pieces INFO-HASH    get pieces info
	  --bitfield INFO-HASH  get bitfield info
	  --files INFO-HASH     get files info
	  --trackers INFO-HASH  get trackers info
	  --peers INFO-HASH     get peers info
	  --start INFO-HASH     start torrent
	  --stop INFO-HASH      stop torrent
	  --delete INFO-HASH    delete torrent
	  --aria2 INFO-HASH     generate aria2 script for downloading
	  --aria2-options OPTIONS
							options to pass to aria2c
	  --xml                 display result as XML
	  
