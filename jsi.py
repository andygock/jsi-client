#!python
"""

/torrents/list.csp?api_key=[40 character api key]
/torrent/information.csp?api_key=[40 character api key]&info_hash=[40 character torrent info hash]
/torrent/files.csp?api_key=[40 character api key]&info_hash=[40 character torrent info hash] 
/torrent/trackers.csp?api_key=[40 character api key]&info_hash=[40 character torrent info hash] 
/torrent/peers.csp?api_key=[40 character api key]&info_hash=[40 character torrent info hash] 

/torrent/add.csp?api_key=[40 character api key]
&url=[url or magnet link]
&info_hash=[40 character torrent info hash]

or a .torrent file as a POST request where the file parameter is named "torrent_file". i'm still running some tests on this, so it might not entirely behave itself, but hey pretty much everything's in alpha anyway...

/torrent/delete.csp?api_key=[40 character api key]&info_hash=[40 character torrent info hash]
/torrent/set_maximum_ratio.csp=[40 character api key]&info_hash=[40 character torrent info hash]&maximum_ratio=[optional decimal] (omitting will set to unlimited)
/torrent/set_name.csp=[40 character api key]&info_hash=[40 character torrent info hash]&name=[optional string] (omitting name will reset to the default torrent name) 

"""

import sys, os
import urllib, urllib2, xmltodict, json, argparse, poster, collections
import re, zlib, StringIO, gzip, bencode
from pprint import pprint

#from __future__ import print_function
#def warning(*objs):
#    print("WARNING: ", *objs, file=sys.stderr)

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'

    def disable(self):
        self.HEADER = ''
        self.OKBLUE = ''
        self.OKGREEN = ''
        self.WARNING = ''
        self.FAIL = ''
        self.ENDC = ''

def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False
    
def hexdump(src, length=16):
    FILTER = ''.join([(len(repr(chr(x))) == 3) and chr(x) or '.' for x in range(256)])
    lines = []
    for c in xrange(0, len(src), length):
        chars = src[c:c+length]
        hex = ' '.join(["%02x" % ord(x) for x in chars])
        printable = ''.join(["%s" % ((ord(x) <= 127 and FILTER[ord(x)]) or '.') for x in chars])
        lines.append("%04x  %-*s  %s\n" % (c, length*3, hex, printable))
    return ''.join(lines)
        
class JustSeedIt():
    
    # Default options
    api_key = ""; # Do not use this, use '.justseedit_api_key' file
    url = "https://api.justseed.it"
    aria2_options = "--file-allocation=none --check-certificate=false --max-concurrent-downloads=8 "+\
        "--continue --max-connection-per-server=8 --min-split-size=1M"
    output_dir = 'd:/Downloads/justseed.it Downloads/'
    ratio = 1.0
    
    def __init__(self, api_key=''):
        self.api_key = "" # start off blank

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
            for keyfile in (self.homedir + '/.justseedit_apikey', '/.justseedit_apikey'):
                # Try different locations for key file
                try:
                    f = open(keyfile,'r') 
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
        
        self.error = False
        self.debug = 0
        self.dry_run = 0
        self.xml_mode = False
        self.torrents = {}
        self.compress = False
        self.edit_opts = []
    
    def quit(self, message):
        print "Error:", message
        print "Quitting."
        sys.exit()
        
    def edit_append(self, option):
        self.edit_opts.append(option)
        return
    
    def xml_from_file(self, file):
        """ Experimental use only """
        f = open(file,'r') 
        xml = f.read()
        return xml
  
    def api(self, page, data={}):
        """ Make a API call using multipart/form-data POST
            Returns XML response on success or False on error
        """
        data['api_key'] = self.api_key
        
        if False:
            print "[DEBUG] Calling {:} with:".format(page)
            for key,value in data.items():
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
                for k,v in headers.items():
                    print "{}: {}".format(k,v)
                
                print "\nBody:\n"
                print hexdump("".join(post_data))
                return "<data>Dry run mode: This is not actual API server response.</data>"
            
            if self.debug:
                sys.stderr.write('Requesting from '+self.url + page + " ... ")

            # Form and make the actual request
            req = urllib2.Request(self.url + page, post_data, headers)
            
            if self.compress:
                # Tell server we can read gzip encoded stream
                req.add_header('Accept-Encoding', 'gzip')
                
            response = urllib2.urlopen(req)
            
            if response.info().get('Content-Encoding') == 'gzip':
                # Server sent gzip encoded stream, uncompress it
                buffer = StringIO.StringIO(response.read())
                f = gzip.GzipFile(fileobj=buffer)
                xml_response = f.read()
            else:
                # Normal uncompressed stream
                xml_response = response.read() # Read server response

            if self.debug:
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
    
    def check_server_response(self,xml_data):
        """ Check server reponse is valid and return True or False. Error is printed to
            stderr if response is not "SUCCESS".
        """
        result = xmltodict.parse(xml_data)
        if result['result']['status'] == 'SUCCESS':
            return True
        else:
            error = urllib.unquote(result['result']['message'])
            sys.stderr.write('Warning: '+error+"\n")
            return False
    
    def id_to_infohash(self, id):
        """ Find the info hash, when given a ID, returns infohash """
        #print self.torrents
        if id in self.torrents:
            if 'info_hash' in self.torrents[id]:
                return self.torrents[id]['info_hash']
            else:
                sys.stderr.write("No info hash available for ID {}\n".format(id))
                return False

        else:
            self.list_update() # Read info from API server
            if id in self.torrents:
                if 'info_hash' in self.torrents[id]:
                    return self.torrents[id]['info_hash']
                else:
                    sys.stderr.write("No info hash available for ID {}\n".format(id))
                    return False
            else:
                sys.stderr.write("No such ID number of '{}'\n".format(id))
                return False
    
    def info(self, infohash):
        """ Grab info about a torrent
        """
        if len(infohash) != 40:
            infohash = self.id_to_infohash(infohash)
            if not infohash:
                return
            
        response_xml = self.api("/torrent/information.csp",{'info_hash': infohash })
        if self.xml_mode:
            print response_xml
            sys.exit()

        result = xmltodict.parse(response_xml)
        for k,v in result['result']['data'].items():
            if k == '@name':
                continue
            if v:
                if k == 'name':
                    # Replace unicode chars with '-' for torrent name only
                    print "{:>24}: {:}".format(k, self.urldecode_to_ascii(v,'replace'))
                else:
                    print "{:>24}: {:}".format(k, self.urldecode_to_ascii(v,'strict'))
            else:
                # No value available for this key
                print "{:>24}:".format(k)
            
        return result

    def urldecode_to_ascii(self,s,error_opt='replace'):
        output = urllib.unquote( s.encode('ascii') ).decode('utf-8').encode('ascii',error_opt)
        
        # Replace '?' with '-'
        if error_opt == 'replace':
            output = re.sub('\?','-',output)
        return output
        
    def pieces(self, infohash):
        if len(infohash) != 40:
            infohash = self.id_to_infohash(infohash)
            if not infohash:
                return            
        response_xml = self.api("/torrent/pieces.csp",{'info_hash': infohash })
        
        if self.xml_mode:
            print response_xml
            sys.exit()

        result = xmltodict.parse(response_xml)
        return result

    def bitfield(self, infohash):
        if len(infohash) != 40:
            infohash = self.id_to_infohash(infohash)
            if not infohash:
                return
                        
        response_xml = self.api("/torrent/bitfield.csp",{'info_hash': infohash })

        if self.xml_mode:
            print response_xml
            sys.exit()

        result = xmltodict.parse(response_xml)
        return result

    def trackers(self, infohash):
        if len(infohash) != 40:
            infohash = self.id_to_infohash(infohash)
            
        response_xml = self.api("/torrent/trackers.csp",{'info_hash': infohash })

        if self.xml_mode:
            print response_xml
            sys.exit()

        result = xmltodict.parse(response_xml)
        return result
    
    def edit(self, infohashes):
        """ Edit torrent. Can change ratio or name
        """
        
        parameters = self.edit_opts
        
        self.list_update()
        
        for infohash in infohashes:
            id = False
            if len(infohash) != 40:
                id = infohash
                infohash = self.id_to_infohash(infohash)
                if not infohash:
                    continue
    
            if 'ratio' in parameters:
                # ratio already set in self.ratio, given my --ratio arg
                if id:
                    sys.stderr.write("Changing ratio of torrent {} to {}\n".format(id,self.ratio))
                else:
                    sys.stderr.write("Changing ratio of torrent {} to {}\n".format(infohash,self.ratio))
                    
                response_xml = self.api("/torrent/set_maximum_ratio.csp",{'info_hash': infohash, 'maximum_ratio': self.ratio })
                if self.xml_mode:
                    print response_xml            
            
            if 'name' in parameters:
                sys.stderr.write("Not implemented.\n");
           
        
        if self.xml_mode:
            sys.exit()
            
        return

    def peers(self, infohash):
        if len(infohash) != 40:
            infohash = self.id_to_infohash(infohash)
            if not infohash:
                return
                       
        response_xml = self.api("/torrent/peers.csp",{'info_hash': infohash })

        if self.xml_mode:
            print response_xml
            sys.exit()

        result = xmltodict.parse(response_xml)
        return result
    
    def start(self, infohash):
        """ Start torrent(s)
            to-do: allow multiple id numbers together, or a range of numbers
        """
        if len(infohash) != 40:
            infohash = self.id_to_infohash(infohash)
            if not infohash:
                return
                    
        response_xml = self.api("/torrent/start.csp",{'info_hash': infohash })

        if self.xml_mode:
            print response_xml
            sys.exit()

        result = xmltodict.parse(response_xml)
        return result

    def stop(self, infohash):
        if len(infohash) != 40:
            infohash = self.id_to_infohash(infohash)
            if not infohash:
                return
                    
        response_xml = self.api("/torrent/stop.csp",{'info_hash': infohash })

        if self.xml_mode:
            print response_xml
            sys.exit()

        result = xmltodict.parse(response_xml)
        return result
    
    def files(self, infohash):
        if len(infohash) != 40:
            infohash = self.id_to_infohash(infohash)
            if not infohash:
                return
                        
        response_xml = self.api("/torrent/files.csp",{'info_hash': infohash })

        if self.xml_mode:
            print response_xml
            sys.exit()

        result = xmltodict.parse(response_xml)
        return result
 
    def files_xml(self, infohash):
        if len(infohash) != 40:
            infohash = self.id_to_infohash(infohash)
            if not infohash:
                return
                        
        response_xml = self.api("/torrent/files.csp",{'info_hash': infohash })
        return response_xml
    
    def download_links(self, infohash):
        """ Get download links fsor infohash or ID number.
            Return list of direct download urls.
        """
        # grab list info, so we can get the torrent name
        self.list_update()

        # if ID number is given as arg instead of infohash then
        # find out the info hash
        if len(infohash) != 40:
            infohash = self.id_to_infohash(infohash)
            if not infohash:
                return
                    
        response_xml = self.api("/torrent/files.csp",{'info_hash': infohash })
        #response_xml = self.xml_from_file('files.xml') # debug
        result = xmltodict.parse(response_xml)
        urls = []
        if 'url' in result['result']['data']['row']:
            # Single file
            urls.append( urllib.unquote(result['result']['data']['row']['url']) )
        else:
            if len(result['result']['data']['row']):
                # Multiple files
                for row in result['result']['data']['row']:
                    if 'url' in row:
                        if row['url']: # It could be None if not available, either that or the field is just missing
                            urls.append( urllib.unquote(row['url']) )
            else:
                # No files for this torrent (possible?)
                sys.stderr.write("This torrent has no files!")
                sys.exit()
                
        if len(urls) == 0:
            sys.stderr.write("There are no download links available for this torrent!")
            sys.exit()
            
        return urls

    def aria2_script(self, infohash, options=None):
        """ Generate a aria2 download script for selected infohash or id number
        """

        # get download links
        urls = self.download_links(infohash)

        if not options:
            options = self.aria2_options

        for url in urls:
            
            #file_path = urllib.unquote( re.sub('https://download.justseed\.it/.{40}/','',url) )
            file_path = self.urldecode_to_ascii(re.sub('https://download.justseed\.it/.{40}/','',url))
            
            output_dir = self.output_dir
            
            if infohash in self.torrents:
                if 'name' in self.torrents[infohash]:
                   output_dir += self.torrents[infohash]['name']
                    
            output_dir = self.urldecode_to_ascii(output_dir)
            
            print "aria2c {} -d \"{}\" -o \"{}\" \"{}\"".format(options, output_dir, file_path, url)
        return
                
    def info_map(self):
        self.list_update()
        print " ID INFOHASH"
        for id, torrent in self.torrents.items():
            print "{:>3} {}".format(id, torrent['info_hash'])
           
    def add_magnet(self,magnets):
        """ Add magnet links defined in list 'magnets'.
            Doesn't return anything
        """
        for magnet in magnets:
            sys.stder.write("Adding magnet link with ratio {}\n".format(self.ratio))
            
            # Check magnet data is valid
            # @todo
                        
            response_xml = self.api("/torrent/add.csp",{'maximum_ratio':str(self.ratio), 'url': magnet })
            if self.xml_mode:
                print response_xml
        return
    
    def add_torrent_file(self,filenames):
        """ Add .torrent files to system. 'filenames' is a list of filenames.
            Doesn't return anything.
        """
        
        for filename in filenames:
        
            sys.stderr.write("Adding torrent file '{}' with ratio {}\n".format(filename, self.ratio))
            
            try:
                f = open(filename,'rb')
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
            
            self.api("/torrent/add.csp",{'torrent_file':data, 'maximum_ratio':str(self.ratio)})
            if self.xml_mode:
                print response_xml
        
        return

    def list_update(self):
        """ Read list information and save in self.torrents
        """
        xml_response = self.api("/torrents/list.csp")
        if xml_response:
            
            # Make new maps
            self.id_to_infohash_map = collections.OrderedDict()
            self.torrents = collections.OrderedDict()
            self.info_map = collections.OrderedDict()
                        
            result = xmltodict.parse(xml_response)
                        
            torrents = result['result']['data']['row']
            
            if 'info_hash' in torrents:
                # Only 1 entry
                self.id_to_infohash_map[torrent['@id']] = torrents['info_hash']
                self.torrents[torrent['@id']] = torrents
            else:
                # More than 1 entry
                if len(torrents):
                    for torrent in torrents:
                        self.id_to_infohash_map[torrent['@id']] = torrent['info_hash']
                        self.torrents[torrent['@id']] = torrent
                else:
                    # No entries, leave var maps as empty 
                    pass
        
        return xml_response
                   
    def list(self):
        """ Show torrents in pretty format
        """
        xml_response = self.list_update()
        if self.xml_mode:
            print xml_response
            sys.exit()
        
        for id, torrent in self.torrents.items():
            # 'name' is a urlencoded UTF-8 string
            # clean this up, many consoles can't dusplay UTF-8, so lets replace unknown chars
            name = self.urldecode_to_ascii(torrent['name'])
            print "[{:>3}] {}".format(torrent['@id'], name)
            if float(torrent['downloaded_as_bytes']) == 0:
                ratio = 0.0
            else:
                ratio = float(torrent['uploaded_as_bytes']) / float(torrent['downloaded_as_bytes'])  
            
            print "{:>30} {:>8} {:>12} {:>.2f} {:>.2f} {}".format(torrent['size_as_string'],
                                                      torrent['percentage_as_decimal'] + "%",
                                                      torrent['elapsed_as_string'],
                                                      ratio,
                                                      float(torrent['maximum_ratio_as_decimal']),
                                                      torrent['status'])                         
        
        result = xmltodict.parse(xml_response)
        print "\nQuota remaining: {}".format(result['result']['data_remaining_as_string'])
        return
    
if __name__ == "__main__":
    # Set up CLI arguments
    parser = argparse.ArgumentParser(prog='jsi.py', description='justseed.it cli client', epilog='')
    parser.add_argument("--aria2", type=str, metavar='INFO-HASH', help='generate aria2 script for downloading')
    parser.add_argument("--aria2-options", type=str, metavar='OPTIONS', help='options to pass to aria2c')
    parser.add_argument("--api-key", type=str, metavar='APIKEY', help='specify 40-char api key')
    parser.add_argument("--bitfield", type=str, metavar='INFO-HASH', help='get bitfield info')
    parser.add_argument("--compress", '-z', action='store_true', help='request api server to use gzip encoding')
    parser.add_argument("-d", "--debug", action='store_true', help='debug mode')
    parser.add_argument("--delete", type=str, metavar='INFO-HASH', help='delete torrent')
    parser.add_argument("--download-links", type=str, metavar='INFO-HASH', help='get download links')
    parser.add_argument("--dry", action='store_true', help='dry run')
    parser.add_argument("-e", "--edit", type=str, nargs='*', metavar='INFO-HASH', help='edit torrent, use with -r or -n')
    parser.add_argument("--files", type=str, metavar='INFO-HASH', help='get files info')
    parser.add_argument("-i", "--info", type=str, metavar='INFOHASH', help='show info for torrent (by infohash or ID)')
    parser.add_argument("--infomap", action='store_true', help='show ID to infohash map')
    parser.add_argument("-l", "--list", action='store_true', help='list torrents')
    parser.add_argument("-m", "--magnet", type=str, nargs='*', help="add torrent using magnet link", metavar='MAGNET-TEXT')
    parser.add_argument("--name", type=float, help='set name (used with -e)')
    parser.add_argument("-p", "--pause", action='store_true', help='pause when finished')
    parser.add_argument("--peers", type=str, metavar='INFO-HASH', help='get peers info')
    parser.add_argument("--pieces", type=str, metavar='INFO-HASH', help='get pieces info')
    parser.add_argument("-t", "--torrent-file", type=str, nargs='*', metavar='TORRENT-FILE', help='add torrent with .torrent file')
    parser.add_argument("--trackers", type=str, metavar='INFO-HASH', help='get trackers info')
    parser.add_argument("-r", "--ratio", type=float, help='set maximum ratio (used in conjunction with -t, -m or -e)')
    parser.add_argument("--start", type=str, metavar='INFO-HASH', help='start torrent')
    parser.add_argument("--stop", type=str, metavar='INFO-HASH', help='stop torrent')
    parser.add_argument("-v", "--verbose", action='store_true', help='verbose mode')
    parser.add_argument("--xml", action='store_true', help='display result as XML')
    
    args = parser.parse_args()
    
    #print args; sys.exit()
    
    if args.api_key:
        jsi = JustSeedIt(args.api_key);
    else:
        jsi = JustSeedIt();
    
    if args.debug:
        jsi.debug = 1
        
    if args.xml:
        jsi.xml_mode = True      

    if args.compress:
        jsi.compress = True    
        
    if args.dry:
        jsi.dry_run = 1
         
    if args.verbose:
        jsi.verbose = True
        
    if args.ratio:
        jsi.ratio = args.ratio
        jsi.edit_append('ratio')

    if args.name:
        sys.stderr.write("--name is not implemented")
        
    # Perform main actions
    
    if args.magnet:
        jsi.add_magnet(args.magnet[0])
        
    elif args.torrent_file:
        jsi.add_torrent_file(args.torrent_file)
        
    elif args.list:
        jsi.list()
        
    elif args.info:
        jsi.info(args.info);

    elif args.edit:
        jsi.edit(args.edit);
 
    elif args.infomap:
        jsi.info_map();

    elif args.pieces:
        print jsi.pieces(args.pieces);

    elif args.start:
        print jsi.start(args.start);
        
    elif args.stop:
        print jsi.stop(args.stop);       

    elif args.delete:
        print "Not implemented"
        #print jsi.delete(args.delete);      
 
    elif args.bitfield:
        print jsi.bitfield(args.bitfield);

    elif args.trackers:
        print jsi.trackers(args.trackers);
    elif args.peers:
        print jsi.peers(args.peers);
         
    elif args.files:
        print jsi.files(args.files);

    elif args.download_links:
        urls = jsi.download_links(args.download_links);
        for line in urls:
            print line
 
    elif args.aria2:
        if args.aria2_options:
            jsi.aria2_options = args.aria2_options     
               
        jsi.aria2_script(args.aria2)
                               
    else:
        parser.print_help()
        
    if args.pause:
        raw_input("Press Enter to continue...")
        
    sys.exit()
   
