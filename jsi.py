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

import sys
import urllib, urllib2, xmltodict, json, argparse, poster, collections
import re, zlib, StringIO, gzip
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
    
    def __init__(self):
        # Obtain API key
        try:
            f = open('.justseedit_api_key','r') 
            key = f.read()
            self.api_key = key.strip()
        except IOError:
            # Could not read api key from file
            # USe default api_key, which is actually an empty string
            pass
        
        self.ratio = 1.0
        self.error = False
        self.debug = 0
        self.dry_run = 0
        self.xml_mode = False
        self.torrents = {}
        self.compress = False
    
    def quit(self, message):
        print "Error:", message
        print "Quitting."
        sys.exit()
        
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
            #print "Warning: ",error
            sys.stderr.write('Warning: '+error+"\n")
            return False
            #self.quit(error)
    
    def id_to_infohash(self, id):
        """ Find the info hash, when given a ID """
        #print self.torrents
        if id in self.torrents:
            if 'info_hash' in self.torrents[id]:
                return self.torrents[id]['info_hash']
            else:
                self.quit("API /information.csp did not contain info hash")

        else:
            self.list_update() # Read info from API server
            if id in self.torrents:
                if 'info_hash' in self.torrents[id]:
                    return self.torrents[id]['info_hash']
                else:
                    self.quit("API /information.csp did not contain info hash")
            else:
                self.quit("No such ID number of '{}'".format(id))
    
    def info(self, infohash):
        """ Grab info about a torrent
        """
        if len(infohash) != 40:
            infohash = self.id_to_infohash(infohash)
            
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
                #print k+":"
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
            
        response_xml = self.api("/torrent/pieces.csp",{'info_hash': infohash })
        
        if self.xml_mode:
            print response_xml
            sys.exit()

        result = xmltodict.parse(response_xml)
        return result

    def bitfield(self, infohash):
        if len(infohash) != 40:
            infohash = self.id_to_infohash(infohash)
            
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

    def set_torrent_ratio(self, infohash, ratio="1.00"):
        if len(infohash) != 40:
            infohash = self.id_to_infohash(infohash)

        if not is_number(ratio):
            sys.stderr.write("Error: Ratio provided '{}' is not numeric.".format(ratio))
            return
            
        response_xml = self.api("/torrent/set_maximum_ratio.csp",{'info_hash': infohash, 'maximum_ratio': ratio })

        if self.xml_mode:
            print response_xml
            sys.exit()

        result = xmltodict.parse(response_xml)
        return result
 
    def peers(self, infohash):
        if len(infohash) != 40:
            infohash = self.id_to_infohash(infohash)
            
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
        
        response_xml = self.api("/torrent/start.csp",{'info_hash': infohash })

        if self.xml_mode:
            print response_xml
            sys.exit()

        result = xmltodict.parse(response_xml)
        return result

    def stop(self, infohash):
        if len(infohash) != 40:
            infohash = self.id_to_infohash(infohash)
        
        response_xml = self.api("/torrent/stop.csp",{'info_hash': infohash })

        if self.xml_mode:
            print response_xml
            sys.exit()

        result = xmltodict.parse(response_xml)
        return result
    
    def files(self, infohash):
        if len(infohash) != 40:
            infohash = self.id_to_infohash(infohash)
            
        response_xml = self.api("/torrent/files.csp",{'info_hash': infohash })

        if self.xml_mode:
            print response_xml
            sys.exit()

        result = xmltodict.parse(response_xml)
        return result
 
    def files_xml(self, infohash):
        if len(infohash) != 40:
            infohash = self.id_to_infohash(infohash)
            
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
            sys.stderr.write("There are no download links availale for this torrent!")
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
            
            if infohash in self.torrents:
                if 'name' in self.torrents[infohash]:
                    self.output_dir += self.torrents[infohash]['name']
                    
            self.output_dir = self.urldecode_to_ascii(self.output_dir)
            print "aria2c {} -d \"{}\" -o \"{}\" \"{}\"".format(options, self.output_dir, file_path, url)
        return
                
    def info_map(self):
        self.list_update()
        print " ID INFOHASH"
        for id, torrent in self.torrents.items():
            print "{:>3} {}".format(id, torrent['info_hash'])
           
    def add_magnet(self,magnet):
        print "Adding magnet link with ratio {}".format(self.ratio)
        response_xml = self.api("/torrent/add.csp",{'maximum_ratio':str(self.ratio), 'url': magnet })
        if self.xml_mode:
            print response_xml
            sys.exit()
        return
    
    def add_torrent_file(self,filename):
        """ Add .torrent file to system.
            Doesn't return anything.
        """
        print "Adding torrent file '{}' with ratio {}".format(filename, self.ratio)
        
        try:
            f = open(filename,'rb')
            data = f.read()
        except IOError:
            sys.stderr.write("Could not open file '{0}'".format(filename))
            return

        self.api("/torrent/add.csp",{'torrent_file':data, 'maximum_ratio':str(self.ratio)})
        if self.xml_mode:
            print response_xml
            sys.exit()        
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
            
            #name = urllib.unquote( torrent['name'].encode('ascii') )
            #name = name.decode('utf-8').encode('ascii','replace')
            
            name = self.urldecode_to_ascii(torrent['name'])
            
            print "[{:>3}] {}".format(torrent['@id'], name)
            if float(torrent['downloaded_as_bytes']) == 0:
                ratio = 0.0
            else:
                ratio = float(torrent['uploaded_as_bytes']) / float(torrent['downloaded_as_bytes'])  
            print "{:>30} {:>8} {:>12} {:>.2f} {}".format(torrent['size_as_string'],
                                                      torrent['percentage_as_decimal'] + "%",
                                                      torrent['elapsed_as_string'],
                                                      ratio,
                                                      torrent['status'],)                         
        
        result = xmltodict.parse(xml_response)
        print "\nQuota remaining: {}".format(result['result']['data_remaining_as_string'])
        
        return

    
if __name__ == "__main__":
    
    # Set up CLI arguments
    parser = argparse.ArgumentParser(prog='jsi.py', description='justseed.it cli client', epilog='')
    parser.add_argument("-m", "--magnet", help="add torrent using magnet link", metavar='MAGNET-TEXT', type=str, nargs=1)
    parser.add_argument("-t", "--torrent-file", type=str, metavar='TORRENT-FILE', help='add torrent with .torrent file')
    parser.add_argument("-i", "--info", type=str, metavar='INFOHASH', help='show info for torrent (by infohash or ID)')
    parser.add_argument("-l", "--list", action='store_true', help='list torrents')
    parser.add_argument("--download-links", type=str, metavar='INFO-HASH', help='get download links')
    parser.add_argument("-p", "--pause", action='store_true', help='pause when finished')
    parser.add_argument("--set-torrent-ratio", type=str, metavar=('INFO-HASH','RATIO'), nargs=2, help='set maximum ratio for torrent')
    parser.add_argument("-r", "--ratio", type=float, help='set maximum ratio (used in conjunction with -t or -m)')
    parser.add_argument("-v", "--verbose", action='store_true', help='verbose mode')
    parser.add_argument("-d", "--debug", action='store_true', help='debug mode')
    parser.add_argument("--dry", action='store_true', help='dry run')
    parser.add_argument("--infomap", action='store_true', help='show ID to infohash map')
    parser.add_argument("--pieces", type=str, metavar='INFO-HASH', help='get pieces info')
    parser.add_argument("--bitfield", type=str, metavar='INFO-HASH', help='get bitfield info')
    parser.add_argument("--files", type=str, metavar='INFO-HASH', help='get files info')
    parser.add_argument("--trackers", type=str, metavar='INFO-HASH', help='get trackers info')
    parser.add_argument("--peers", type=str, metavar='INFO-HASH', help='get peers info')
    parser.add_argument("--start", type=str, metavar='INFO-HASH', help='start torrent')
    parser.add_argument("--stop", type=str, metavar='INFO-HASH', help='stop torrent')
    parser.add_argument("--delete", type=str, metavar='INFO-HASH', help='delete torrent')
    parser.add_argument("--aria2", type=str, metavar='INFO-HASH', help='generate aria2 script for downloading')
    parser.add_argument("--aria2-options", type=str, metavar='OPTIONS', help='options to pass to aria2c')
    
    parser.add_argument("--xml", action='store_true', help='display result as XML')
    parser.add_argument("--compress", '-z', action='store_true', help='request api server to use gzip encoding')
    
    args = parser.parse_args()
    
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
    
    # Perform main action
    
    if args.magnet:
        jsi.add_magnet(args.magnet[0])
        
    elif args.torrent_file:
        jsi.add_torrent_file(args.torrent_file)
        
    elif args.list:
        jsi.list()
        
    elif args.info:
        jsi.info(args.info);
 
    elif args.infomap:
        jsi.info_map();

    elif args.set_torrent_ratio:
        # jsi.py --set-torrent-ratio ID RATIO
        jsi.set_torrent_ratio(args.set_torrent_ratio[0], args.set_torrent_ratio[1]);
        if not jsi.error:
            sys.stderr.write("Ratio of selected torrent was successfully changed.")

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
   
