#!/usr/bin/env python
"""

jsi.py

Unofficial justseed.it cli client

"""

import sys
import os
import urllib
import urllib2
#import xmltodict
import json
import argparse
import poster
import collections
import re
#import zlib
import StringIO
import gzip
import bencode
#from pprint import pprint
from colorama import init, Fore, Back, Style
from collections import OrderedDict
from xml.dom import minidom

JSI_VERSION = "0.0"


def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False
    

def hexdump(src, length=16):
    hdfilter = ''.join([(len(repr(chr(x))) == 3) and chr(x) or '.' for x in range(256)])
    lines = []
    for c in xrange(0, len(src), length):
        chars = src[c:c+length]
        hex_buffer = ' '.join(["%02x" % ord(x) for x in chars])
        printable = ''.join(["%s" % ((ord(x) <= 127 and hdfilter[ord(x)]) or '.') for x in chars])
        lines.append("%04x  %-*s  %s\n" % (c, length*3, hex_buffer, printable))
    return ''.join(lines)
        

class JustSeedIt():
    
    # Default options
    
    DEFAULT_API_SERVER = "https://api.justseed.it"
    DEFAULT_ARIA2_OPTIONS = "--file-allocation=none --check-certificate=false --max-concurrent-downloads=8 " + \
        "--continue --max-connection-per-server=8 --min-split-size=1M"
    DEFAULT_DOWNLOAD_DIR = 'd:/Downloads/justseed.it Downloads/'
    DEFAULT_RATIO = 1.0
    
    def __init__(self, api_key=''):
        self.api_key = ""  # start off blank

        if self.api_key != "":
            self.api_key = api_key
            if self.api_key == "":
                # No found in file searches above
                sys.stderr.write("Error: Specified API key with --api-key was blank")
                sys.exit()
              
        else:
            # Get homedir
            self.homedir = os.path.expanduser("~")
            
            # Obtain API key
            for keyfile in [self.homedir + '/.justseedit_apikey',
                            os.path.dirname(os.path.realpath(__file__)) + '/.justseedit_apikey']:
                # Try different locations for key file
                try:
                    f = open(keyfile, 'r')
                    key = f.read()
                    self.api_key = key.strip()
                    #sys.stderr.write("Read API key from '{}'\n".format(keyfile))
                    break
                except IOError:
                    # Could not read api key from file
                    # Use default api_key, which is actually an empty string
                    continue
        
            if self.api_key == "":
                # No found in file searches above
                sys.stderr.write("Error: No API key file could be found or was specified")
                sys.exit()
        
        # Set default configs, these may be changed later
        self.url = self.DEFAULT_API_SERVER
        self.aria2_options = self.DEFAULT_ARIA2_OPTIONS
        self.output_dir = self.DEFAULT_DOWNLOAD_DIR
        self.ratio = self.DEFAULT_DOWNLOAD_DIR
        
        self.error = False
        self.debug = 0
        self.dry_run = 0
        self.xml_mode = False
        self.torrents = None
        self.compress = False
        self.edit_opts = []
        self.verbose = False

        self.xml_response = ''

        self.id_to_infohash_map = collections.OrderedDict()
        self.torrents = collections.OrderedDict()
        #self.info_map = collections.OrderedDict()

        self.data_remaining_as_bytes = 0
        self.data_remaining_as_string = 0

    @staticmethod
    def pretty_print(data):
        print(json.dumps(data, indent=4))

    @staticmethod
    def quit(message):
        print "Error:", message
        print "Quitting."
        sys.exit()
        
    def edit_append(self, option):
        self.edit_opts.append(option)
        return

    @staticmethod
    def xml_from_file(filename):
        """ Experimental use only """
        f = open(filename, 'r')
        xml = f.read()
        return xml
  
    def api(self, page, data=None):
        """ Make a API call using multipart/form-data POST
            Returns XML response on success or False on error
        """
        if not data:
            data = {}
        data['api_key'] = self.api_key
        
        if False:
            print "[DEBUG] Calling {:} with:".format(page)
            for key, value in data.items():
                #print key, value
                print "{:>15}: {:}".format(key, value)
        
        try:
            # for application/x-www-form-urlencoded
            #post_data = urllib.urlencode( data ) 
            #req = urllib2.Request(self.url + page, post_data)
            
            # for multipart/form-data
            poster.streaminghttp.register_openers()
            post_data, headers = poster.encode.multipart_encode(data)

            if self.dry_run:
                print "\nHeaders:\n"
                #print headers
                for k, v in headers.items():
                    print "{}: {}".format(k, v)
                
                print "\nBody:\n"
                print hexdump("".join(post_data))
                return "<data>Dry run mode: This is not actual API server response.</data>"
            
            if self.verbose or self.debug:
                sys.stderr.write('Requesting from '+self.url + page + " ... ")

            # Form and make the actual request
            req = urllib2.Request(self.url + page, post_data, headers)
            
            if self.compress:
                # Tell server we can read gzip encoded stream
                req.add_header('Accept-Encoding', 'gzip')
                
            response = urllib2.urlopen(req)
            
            if response.info().get('Content-Encoding') == 'gzip':
                # Server sent gzip encoded stream, uncompress it
                gzbuffer = StringIO.StringIO(response.read())
                f = gzip.GzipFile(fileobj=gzbuffer)
                xml_response = f.read()
            else:
                # Normal uncompressed stream
                xml_response = response.read()  # Read server response

            if self.verbose or self.debug:
                # Tell user the response was read
                sys.stderr.write("OK\n")

            # Store xml for later use, maybe we might use it
            self.xml_response = xml_response

        except urllib2.URLError, urllib2.HTTPError:
            sys.stderr.write("Error: URL or HTTP error\n")
            sys.exit()
        
        if self.check_server_response(xml_response):
            # Server responded with "SUCCESS"
            self.error = False
            return xml_response
        else:
            # Server did NOT respond with "SUCCESS"
            # self.check_server_response() will already display an error message
            self.error = True
            return False

    @staticmethod
    def check_server_response(xml_data):
        """ Check server response is valid and return True or False. Error is printed to
            stderr if response is not "SUCCESS".
        """
        status = minidom.parseString(xml_data).getElementsByTagName("status")[0].firstChild.nodeValue
        if status == 'SUCCESS':
            return True
        else:
            error = urllib.unquote(minidom.parseString(xml_data).getElementsByTagName("message")[0].firstChild.nodeValue)
            sys.stderr.write('Warning: '+error+"\n")
            return False
    
    def id_to_infohash(self, torrent_id):
        """ Find the info hash, when given a ID, returns infohash """
        if torrent_id in self.id_to_infohash_map:
            # There is a matching info hash found for this ID
            return self.id_to_infohash_map[torrent_id]
        else:
            self.list_update()  # Read info from API server
            if torrent_id in self.id_to_infohash_map:
                return self.id_to_infohash_map[torrent_id]
            else:
                sys.stderr.write("Error: No info hash available for ID {}\n".format(torrent_id))
                return False

    def info(self, infohash):
        """ Grab info about a torrent
        """
        if len(infohash) != 40:
            infohash = self.id_to_infohash(infohash)
            if not infohash:
                return
            
        xml_response = self.api("/torrent/information.csp", {'info_hash': infohash})
        if self.xml_mode:
            print xml_response
            sys.exit()

        data = minidom.parseString(xml_response)
        for element in data.getElementsByTagName('data')[0].childNodes:
            if element.nodeType == element.ELEMENT_NODE:
                key = element.nodeName
                try:
                    value = data.getElementsByTagName(element.nodeName)[0].firstChild.nodeValue
                except AttributeError:
                    value = ""

                # Print all elements and values
                if key == 'name':
                    # Replace unicode chars with '-' for torrent name only
                    print "{:>24}: {:}".format(key, self.urldecode_to_ascii(value, 'replace'))
                else:
                    print "{:>24}: {:}".format(key, self.urldecode_to_ascii(value, 'strict'))

        return xml_response

    @staticmethod
    def urldecode_to_ascii(s, error_opt='replace'):
        output = urllib.unquote(s.encode('ascii')).decode('utf-8').encode('ascii', error_opt)
        
        # Replace '?' with '-'
        if error_opt == 'replace':
            output = re.sub('\?', '-', output)
        return output
        
    def pieces(self, infohash):
        if len(infohash) != 40:
            infohash = self.id_to_infohash(infohash)
            if not infohash:
                return            
        response_xml = self.api("/torrent/pieces.csp", {'info_hash': infohash})
        
        if self.xml_mode:
            print response_xml
            sys.exit()

        #result = xmltodict.parse(response_xml)
        return response_xml

    def bitfield(self, infohash):
        if len(infohash) != 40:
            infohash = self.id_to_infohash(infohash)
            if not infohash:
                return
                        
        response_xml = self.api("/torrent/bitfield.csp", {'info_hash': infohash})

        if self.xml_mode:
            print response_xml
            sys.exit()

        return response_xml

    def trackers(self, infohash):
        if len(infohash) != 40:
            infohash = self.id_to_infohash(infohash)
            if not infohash:
                return
            
        response_xml = self.api("/torrent/trackers.csp", {'info_hash': infohash})

        if self.xml_mode:
            print response_xml
            sys.exit()

        return response_xml
    
    def edit(self, infohashes):
        """ Edit torrent. Can change ratio or name
        """
        
        parameters = self.edit_opts
        
        self.list_update()
        
        if not isinstance(infohashes, list):
            infohashes = [infohashes]

        for infohash in infohashes:
            torrent_id = False
            if len(infohash) != 40:
                torrent_id = infohash
                infohash = self.id_to_infohash(infohash)
                if not infohash:
                    continue
    
            if 'ratio' in parameters:
                # ratio already set in self.ratio, given my --ratio arg
                if torrent_id:
                    sys.stderr.write("Changing ratio of torrent {} to {}\n".format(torrent_id, self.ratio))
                else:
                    sys.stderr.write("Changing ratio of torrent {} to {}\n".format(infohash, self.ratio))
                    
                response_xml = self.api("/torrent/set_maximum_ratio.csp",
                                        {'info_hash': infohash, 'maximum_ratio': self.ratio})
                if self.xml_mode:
                    print response_xml            
            
            if 'name' in parameters:
                sys.stderr.write("Not implemented.\n")
        
        if self.xml_mode:
            sys.exit()
            
        return

    def peers(self, infohash):
        if len(infohash) != 40:
            infohash = self.id_to_infohash(infohash)
            if not infohash:
                return
                       
        response_xml = self.api("/torrent/peers.csp", {'info_hash': infohash})

        if self.xml_mode:
            print response_xml
            sys.exit()

        return response_xml
    
    def start(self, infohashes):
        """ Start torrent(s)
        """

        self.list_update()

        for infohash in infohashes:
            torrent_id = infohash
            if len(infohash) != 40:
                infohash = self.id_to_infohash(infohash)
                if not infohash:
                    continue

            if self.verbose or self.debug:
                sys.stderr.write("Starting torrent: {}\n".format(torrent_id))

            response_xml = self.api("/torrent/start.csp", {'info_hash': infohash})

            if self.xml_mode:
                print response_xml
                continue

        return

    def stop(self, infohashes):
        """ Stop torrent(s)
        """

        self.list_update()

        for infohash in infohashes:
            torrent_id = infohash
            if len(infohash) != 40:
                infohash = self.id_to_infohash(infohash)
                if not infohash:
                    continue
            
            if self.verbose or self.debug:
                sys.stderr.write("Stopping torrent: {}\n".format(torrent_id))

            response_xml = self.api("/torrent/stop.csp", {'info_hash': infohash})

            if self.xml_mode:
                print response_xml
                continue

        return
    
    def files(self, infohash):
        if len(infohash) != 40:
            infohash = self.id_to_infohash(infohash)
            if not infohash:
                return

        response_xml = self.api("/torrent/files.csp", {'info_hash': infohash})

        if self.xml_mode:
            print response_xml
            sys.exit()

        return response_xml
 
    def files_xml(self, infohash):
        if len(infohash) != 40:
            infohash = self.id_to_infohash(infohash)
            if not infohash:
                return
                        
        response_xml = self.api("/torrent/files.csp", {'info_hash': infohash})
        return response_xml
    
    def download_links(self, infohashes):
        """ Get download links for infohash or ID number.
            Return list of direct download urls.
        """
        # grab list info, so we can get the torrent name
        self.list_update()

        url_list = []

        #print self.torrents

        for infohash in infohashes:
            if len(infohash) != 40:
                infohash = self.id_to_infohash(infohash)
                if not infohash:
                    continue

        self.api("/torrent/files.csp", {'info_hash': infohash})

        rows = minidom.parseString(self.xml_response).getElementsByTagName("row")
        self.file_data = rows
        for row in rows:
            url_list.append(urllib.unquote(row.getElementsByTagName('url')[0].firstChild.nodeValue))

        return url_list

    def aria2_script(self, infohashes, options=None):
        """ Generate a aria2 download script for selected infohash or id number
        """

        for infohash in infohashes:
            # get download links

            if len(infohash) != 40:
                infohash = self.id_to_infohash(infohash)
                if not infohash:
                    continue

            url_list = self.download_links([infohash])

            # Get torrent name, based in info hash, to use in output dir
            name = ''
            for torrent in self.torrents:
                if torrent.getElementsByTagName('info_hash')[0].firstChild.nodeValue == infohash:
                    name = torrent.getElementsByTagName('name')[0].firstChild.nodeValue
                    print name

            if name == '':
                sys.stderr.write("Error: Could not find torrent name, for this info hash. Skipping\n")
                continue

            if not options:
                options = self.aria2_options
    
            for url in url_list:
                file_path = self.urldecode_to_ascii(re.sub('https://download.justseed\.it/.{40}/', '', url))
                output_dir = self.output_dir + name
                output_dir = self.urldecode_to_ascii(output_dir)
                print "aria2c {} -d \"{}\" -o \"{}\" \"{}\"".format(options, output_dir, file_path, url)
        return
                
    #def info_map(self):
    #    self.list_update()
    #    print " ID INFOHASH"
    #    for torrent_id, torrent in self.torrents.items():
    #        print "{:>3} {}".format(torrent_id, torrent['info_hash'])
           
    def add_magnet(self, magnets):
        """ Add magnet links defined in list 'magnets'.
            Doesn't return anything
        """
        for magnet in magnets:
            sys.stderr.write("Adding magnet link with ratio {}\n".format(self.ratio))
            
            # Check magnet data is valid
            # @todo
                        
            response_xml = self.api("/torrent/add.csp", {'maximum_ratio': str(self.ratio), 'url': magnet})
            if self.xml_mode:
                print response_xml
        return
    
    def add_torrent_file(self, filenames):
        """ Add .torrent files to system. 'filenames' is a list of filenames.
            Doesn't return anything.
        """
        
        for filename in filenames:
        
            sys.stderr.write("Adding torrent file '{}' with ratio {}\n".format(filename, self.ratio))
            
            try:
                f = open(filename, 'rb')
                data = f.read()
            except IOError:
                sys.stderr.write("Could not open file '{0}'".format(filename))
                continue
    
            # Check .torrent file data is valid
            try:
                bencode.bdecode(data)
            except bencode.BTL.BTFailure:
                sys.stderr.write("Error: Ignoring '{}', not a valid .torrent file!\n".format(filename))
                continue
            
            self.api("/torrent/add.csp", {'torrent_file': data, 'maximum_ratio': str(self.ratio)})

            if self.xml_mode:
                print self.xml_response
                continue
        
        return

    def list_update(self):
        """ Read list information and save in self.torrents
        """
        
        if not self.torrents:
            xml_response = self.api("/torrents/list.csp")
            
            if not xml_response:
                return
        
            # Make new maps
            self.id_to_infohash_map = collections.OrderedDict()
            #self.info_map = collections.OrderedDict()
                        
            #result = xmltodict.parse(xml_response)

            #print xml_response
            self.torrents = minidom.parseString(xml_response).getElementsByTagName("row")
            for row in self.torrents:
                # Each torrent
                self.id_to_infohash_map[row.getAttribute('id')] = row.getElementsByTagName('info_hash')[0].firstChild.nodeValue

            self.data_remaining_as_bytes = minidom.parseString(xml_response).getElementsByTagName("data_remaining_as_bytes")[0].firstChild.nodeValue
            self.data_remaining_as_string = minidom.parseString(xml_response).getElementsByTagName("data_remaining_as_string")[0].firstChild.nodeValue

        else:
            # list already up to date
            # don't need to do anything
            pass
        
        return self.xml_response
                   
    def list(self):
        """ Show torrents in pretty format
        """
        xml_response = self.list_update()
        if self.xml_mode:
            print xml_response
            sys.exit()
        
        #for torrent_id, torrent in self.torrents.items():
        for torrent in self.torrents:

            # 'name' is a urlencoded UTF-8 string
            # clean this up, many consoles can't display UTF-8, so lets replace unknown chars
            name = self.urldecode_to_ascii(torrent.getElementsByTagName('name')[0].firstChild.nodeValue)
            id = torrent.getAttribute("id")

            # Print torrent name
            print Fore.CYAN + "[" + Fore.RESET + "{:>3}".format(id) +\
                  Fore.CYAN + "] {}".format(name) + Fore.RESET
            
            if float(torrent.getElementsByTagName('downloaded_as_bytes')[0].firstChild.nodeValue) == 0:
                ratio = 0.0
            else:
                ratio = float(torrent.getElementsByTagName('uploaded_as_bytes')[0].firstChild.nodeValue) / float(torrent.getElementsByTagName('downloaded_as_bytes')[0].firstChild.nodeValue)
            
            status = torrent.getElementsByTagName('status')[0].firstChild.nodeValue
            if status == 'stopped':
                # Show progress in RED if stopped
                status = Fore.RED + status + Fore.RESET
            else:
                if torrent.getElementsByTagName('percentage_as_decimal')[0].firstChild.nodeValue != "100.0":
                    # Show status in GREEN, if progress is under 100%
                    status = Fore.GREEN + status + Fore.RESET
                
            print "{:>30} {:>8} {:>12} {:.2f} {:5.2f} {}".format(torrent.getElementsByTagName('size_as_string')[0].firstChild.nodeValue,
                                                                 torrent.getElementsByTagName('percentage_as_decimal')[0].firstChild.nodeValue + "%",
                                                                 torrent.getElementsByTagName('elapsed_as_string')[0].firstChild.nodeValue,
                                                                 ratio,
                                                                 float(torrent.getElementsByTagName('maximum_ratio_as_decimal')[0].firstChild.nodeValue),
                                                                 status)
        
        print "\nQuota remaining: {}".format(self.data_remaining_as_string)
        return
    
if __name__ == "__main__":
    # Set up CLI arguments
    parser = argparse.ArgumentParser(prog='jsi.py', description='justseed.it cli client, version ' + JSI_VERSION, epilog='When INFO-HASH is asked as a parameter, a torrent ID may also be used. This corresponding ID number is shown in the first column of the --list output.')
    
    parser.add_argument("--aria2", type=str, nargs='*', metavar='INFO-HASH', help='generate aria2 script for downloading')
    parser.add_argument("--aria2-options", type=str, metavar='OPTIONS', help='options to pass to aria2c (default: "{}")'.format(JustSeedIt.DEFAULT_ARIA2_OPTIONS))
    parser.add_argument("--api-key", type=str, metavar='APIKEY', help='specify 40-char api key')
    parser.add_argument("--bitfield", type=str, metavar='INFO-HASH', help='get bitfield info')
    parser.add_argument("-d", "--debug", action='store_true', help='debug mode')
    #parser.add_argument("--delete", type=str, metavar='INFO-HASH', help='delete torrent')
    parser.add_argument("--download-links", "--dl", type=str, nargs='*', metavar='INFO-HASH', help='get download links')
    parser.add_argument("--dry", action='store_true', help='dry run')
    parser.add_argument("-e", "--edit", type=str, nargs='*', metavar='INFO-HASH', help='edit torrent, use with -r or -n')
    parser.add_argument("--files", type=str, metavar='INFO-HASH', help='get files info')
    parser.add_argument("-i", "--info", type=str, metavar='INFO-HASH', help='show info for torrent')
    #parser.add_argument("--infomap", action='store_true', help='show ID to infohash map')
    parser.add_argument("-l", "--list", action='store_true', help='list torrents')
    parser.add_argument("-m", "--magnet", type=str, nargs='*', help="add torrent using magnet link", metavar='MAGNET-TEXT')
    parser.add_argument("--name", type=float, help='set name (used with -e)')
    parser.add_argument("-o", "--output-dir", type=str, help='set output dir for aria2 scripts (default: "{}")'.format(JustSeedIt.DEFAULT_DOWNLOAD_DIR))
    parser.add_argument("-p", "--pause", action='store_true', help='pause when finished')
    parser.add_argument("--peers", type=str, metavar='INFO-HASH', help='get peers info')
    parser.add_argument("--pieces", type=str, metavar='INFO-HASH', help='get pieces info')
    parser.add_argument("-t", "--torrent-file", type=str, nargs='*', metavar='TORRENT-FILE', help='add torrent with .torrent file')
    parser.add_argument("--trackers", type=str, metavar='INFO-HASH', help='get trackers info')
    parser.add_argument("-r", "--ratio", type=float, help='set maximum ratio, used in conjunction with -t, -m or -e (default: {})'.format(str(JustSeedIt.DEFAULT_RATIO)))
    parser.add_argument("--start", type=str, nargs='*', metavar='INFO-HASH', help='start torrent')
    parser.add_argument("--stop", type=str, nargs='*', metavar='INFO-HASH', help='stop torrent')
    parser.add_argument("-v", "--verbose", action='store_true', help='verbose mode')
    parser.add_argument("--xml", action='store_true', help='display result as XML')
    parser.add_argument("-z", "--compress", action='store_true', help='request api server to use gzip encoding')

    # set up coloring with colorama
    terminal = os.getenv('TERM')
    if terminal == 'rxvt' or terminal == 'xterm':
        # Cygwin, xterm emulators
        init(autoreset=True, convert=False, strip=False)
        
    else:
        # Standard windows console
        init(autoreset=True)

    args = parser.parse_args()
    #print args; sys.exit()
    
    if args.api_key:
        jsi = JustSeedIt(args.api_key)
    else:
        jsi = JustSeedIt()
    
    if args.debug:
        jsi.debug = 1
        
    if args.verbose:
        jsi.verbose = True
                
    if args.xml:
        jsi.xml_mode = True      

    if args.compress:
        jsi.compress = True    
        
    if args.dry:
        jsi.dry_run = 1
         
    if args.aria2_options:
        jsi.aria2_options = args.aria2_options

    if args.output_dir:
        jsi.output_dir = args.output_dir
    else:
        # output dir can be defined in env
        if os.getenv('JSI_OUTPUT_DIR'):
            jsi.output_dir = os.getenv('JSI_OUTPUT_DIR')
        
    if args.ratio:
        jsi.ratio = args.ratio
        jsi.edit_append('ratio')

    if args.name:
        sys.stderr.write("--name is not implemented")
        sys.exit()
        
    # Perform main actions
    
    if args.magnet:
        jsi.add_magnet(args.magnet[0])
        
    elif args.torrent_file:
        jsi.add_torrent_file(args.torrent_file)
        
    elif args.list:
        jsi.list()
        
    elif args.info:
        jsi.info(args.info)

    elif args.edit:
        jsi.edit(args.edit)
 
    #elif args.infomap:
    #    jsi.info_map()

    elif args.pieces:
        print jsi.pieces(args.pieces)

    elif args.start:
        jsi.start(args.start)

    elif args.stop:
        jsi.stop(args.stop)

    #elif args.delete:
        #print "Not implemented"
        #print jsi.delete(args.delete)
 
    elif args.bitfield:
        jsi.bitfield(args.bitfield)
        print "Pieces: " + minidom.parseString(jsi.xml_response).getElementsByTagName('pieces')[0].firstChild.nodeValue
        print "Bitfield: " + minidom.parseString(jsi.xml_response).getElementsByTagName('bitfield')[0].firstChild.nodeValue

    elif args.trackers:
        jsi.trackers(args.trackers)
        rows = minidom.parseString(jsi.xml_response).getElementsByTagName("row")
        for row in rows:
            print urllib.unquote(row.getElementsByTagName('url')[0].firstChild.nodeValue) +\
                  " Seeders: " + row.getElementsByTagName('seeders')[0].firstChild.nodeValue +\
                  " Peers: " + row.getElementsByTagName('peers')[0].firstChild.nodeValue +\
                  " Leechers: " + row.getElementsByTagName('leechers')[0].firstChild.nodeValue

    elif args.peers:
        data = jsi.peers(args.peers)
        print "Not implemented yet."
        #print data['result']['data']
         
    elif args.files:
        # trying out minidom parsing
        jsi.files(args.files)
        rows = minidom.parseString(jsi.xml_response).getElementsByTagName("row")
        print "Number of files: " + str(len(rows))
        for row in rows:
            print "\"" + row.getElementsByTagName('path')[0].firstChild.nodeValue + "\" " +\
                  row.getElementsByTagName('size_as_bytes')[0].firstChild.nodeValue + " " +\
                  urllib.unquote(row.getElementsByTagName('url')[0].firstChild.nodeValue)

    elif args.download_links:
        urls = jsi.download_links(args.download_links)
        for line in urls:
            print line
 
    elif args.aria2:
        if args.aria2_options:
            jsi.aria2_options = args.aria2_options
        elif os.getenv('JSI_ARIA2_OPTIONS'):
            jsi.aria2_options = os.getenv('JSI_ARIA2_OPTIONS')

        jsi.aria2_script(args.aria2)
                               
    else:
        parser.print_help()
        
    if args.pause:
        raw_input("Press Enter to continue...")
        
    sys.exit()