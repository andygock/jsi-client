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
import urllib, urllib2, xmltodict, json, argparse, poster, collections, re
from pprint import pprint

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
    aria2_options = "--file-allocation=none --check-certificate=false --max-concurrent-downloads=4 --continue --max-connection-per-server=4"
    
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
        self.info_map = {}
    
    def quit(self, message):
        print "Error:", message
        print "Quitting."
        sys.exit()
        
    def xml_from_file(self, file):
        f = open(file,'r') 
        xml = f.read()
        return xml
    
    def list_xml(self):
        xml = self.api("/torrents/list.csp")
        self.xml_list = xml
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
            
            req = urllib2.Request(self.url + page, post_data, headers)
            
            response = urllib2.urlopen(req)
            xml_response = response.read()
            self.xml_response = xml_response

        except urllib2.URLError, urllib2.HTTPError:
            print "URL or HTTP error"
            sys.exit()
        
        if self.check_server_response(xml_response):
            self.error = False
            #if self.debug:
            #    print xml_response
            return xml_response
        else:
            self.error = True
            return False
    
    def check_server_response(self,xml_data):
        result = xmltodict.parse(xml_data)
        if result['result']['status'] == 'SUCCESS':
            return True
        else:
            error = urllib.unquote(result['result']['message'])
            print "Warning: ",error
            return False
            #self.quit(error)
    
    def id_to_infohash(self, id):
        #pprint(self.id_to_infohash_map)
        try:
            self.list_only()
            return self.id_to_infohash_map[id]
        except KeyError:
            self.quit("No such ID number of '{}'".format(id))
    
    def info(self, infohash):
        if len(infohash) != 40:
            infohash = self.id_to_infohash(infohash)
            
        response_xml = self.api("/torrent/information.csp",{'info_hash': infohash })
        print response_xml
        
        result = xmltodict.parse(xml_response)
        return
        #result['data']
        
    def pieces(self, infohash):
        if len(infohash) != 40:
            infohash = self.id_to_infohash(infohash)
            
        response_xml = self.api("/torrent/pieces.csp",{'info_hash': infohash })
        return response_xml

    def bitfield(self, infohash):
        if len(infohash) != 40:
            infohash = self.id_to_infohash(infohash)
            
        response_xml = self.api("/torrent/bitfield.csp",{'info_hash': infohash })
        return response_xml

    def files(self, infohash):
        if len(infohash) != 40:
            infohash = self.id_to_infohash(infohash)
            
        response_xml = self.api("/torrent/files.csp",{'info_hash': infohash })
        #print response_xml
        result = xmltodict.parse(response_xml)
        return response_xml
 
    def files_xml(self, infohash):
        if len(infohash) != 40:
            infohash = self.id_to_infohash(infohash)
            
        response_xml = self.api("/torrent/files.csp",{'info_hash': infohash })
        result = xmltodict.parse(response_xml)
        return response_xml
    
    def download_links(self, infohash):
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
            # Multiple files
            for row in result['result']['data']['row']:
                if 'url' in row:
                    urls.append( urllib.unquote(row['url']) )
        return urls

    def aria2_script(self, infohash):
        urls = self.download_links(infohash)
        #pprint(self.id_to_infohash_map)
        for url in urls:
            file_path = urllib.unquote( re.sub('https://download.justseed\.it/.{40}/','',url) )
            #print file_path
            self.output_dir = 'd:/Downloads/justseed.it Downloads/'
            #pprint(self.torrents)
            if infohash in self.torrents:
                if 'name' in self.torrents[infohash]:
                    self.output_dir += self.torrents[infohash]['name']
            
            print "aria2c {} -d \"{}\" -o \"{}\" \"{}\"".format(self.aria2_options, self.output_dir, file_path, url)
        return
                
    def info_xml(self, infohash):
        response_xml = self.api("/torrent/information.csp",{'info_hash': infohash })
        print response_xml
        return
        
    def info_map(self):
        self.list_only()
        print " ID INFOHASH"
        for id, infohash in self.id_to_infohash_map.items():
            print "{:>3} {}".format(id, infohash)
           
    def add_magnet(self,magnet):
        print "Adding magnet link with ratio {}".format(self.ratio)
        response_xml = self.api("/torrent/add.csp",{'maximum_ratio':str(self.ratio), 'url': magnet })
        print response_xml
        return
    
    def add_torrent_file(self,filename):
        """ Add .torrent file to system
        """
        print "Adding from file '{}' with ratio {}".format(filename, self.ratio)
        
        try:
            f = open(filename,'rb')
            data = f.read()
            
        except IOError:
            print "Could not open file '{0}'".format(filename)
            return
        
        try:
            xml_response = self.api("/torrent/add.csp",{'torrent_file':data, 'maximum_ratio':str(self.ratio)})
            self.xml_response = xml_response
        except urllib2.URLError, urllib2.HTTPError:
            print "Could not communicate with API server, or response from it was unexpected"
            sys.exit()
        
        return

    def list_only(self):
        xml_response = self.api("/torrents/list.csp")
        #print xml_response
        if xml_response:
            result = xmltodict.parse(xml_response)
            torrents = result['result']['data']['row']
            
            # Make new maps
            self.id_to_infohash_map = collections.OrderedDict()
            self.torrents = collections.OrderedDict()
            self.info_map = collections.OrderedDict()
            
            #pprint(torrents)
            
            for torrent in torrents:
                
                
                self.id_to_infohash_map[torrent['@id']] = torrent['info_hash']
                
                self.torrents[torrent['@id']] = { 'info_hash': torrent['info_hash'],
                                                  'name': torrent['name'],
                                                  'label': torrent['label'],
                                                  'status': torrent['status'] }
                
                """
                self.info_map[torrent['@id']]['name'] = torrent['name']
                
                #pprint(self.info_map)
                
                self.info_map[torrent['@id']]['label'] = torrent['label']
                self.info_map[torrent['@id']]['status'] = torrent['status']
                
                self.info_map[torrent['info_hash']]['name'] = torrent['name']
                self.info_map[torrent['info_hash']]['label'] = torrent['label']
                self.info_map[torrent['info_hash']]['status'] = torrent['status']
                """
                
                                
            #if self.debug:
            #pprint(self.torrents)
        
            
        
        return
                   
    def list(self):
        """ Show torrents in pretty format
        """
        
        print "Getting list of torrents..."
        
        #xml_response = self.xml_from_file("list.xml")
        xml_response = self.api("/torrents/list.csp")
        if xml_response:
            result = xmltodict.parse(xml_response)
            #print result
            #return
        
            torrents = result['result']['data']['row']
            self.id_to_infohash_map = collections.OrderedDict()
            for torrent in torrents:
                self.id_to_infohash_map[torrent['@id']] = torrent['info_hash']
                
                print "[{:>3}] {}".format(torrent['@id'], urllib.unquote(torrent['name']))
                
                if float(torrent['downloaded_as_bytes']) == 0:
                    ratio = 0.0
                else:
                    ratio = float(torrent['uploaded_as_bytes']) / float(torrent['downloaded_as_bytes'])
                #print ratio
                
                print "{:>40} {:>8} {:>12} {:>.2f}".format(torrent['size_as_string'],
                                                          torrent['percentage_as_decimal'] + "%",
                                                          torrent['elapsed_as_string'],
                                                          ratio)
                #print json.dumps(result['result']['data'], indent=4)

    
if __name__ == "__main__":
    
    # Set up CLI arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--magnet", help="add torrent using magnet link", metavar='MAGNET-TEXT', type=str, nargs=1)
    parser.add_argument("-t", "--torrent-file", type=str, metavar='TORRENT-FILE', help='add torrent with .torrent file')
    parser.add_argument("-i", "--info", type=str, metavar='INFOHASH', help='show info for torrent (by infohash or ID)')
    parser.add_argument("-l", "--list", action='store_true', help='list torrents')
    parser.add_argument("--list-xml", action='store_true', help='list torrents in raw XML format')
    parser.add_argument("--download-links", type=str, metavar='INFO-HASH', help='get download links')
    parser.add_argument("-p", "--pause", action='store_true', help='pause when finished')
    parser.add_argument("-r", "--ratio", type=float, help='set maximum ratio (used in conjunction with -t or -m)')
    parser.add_argument("-v", "--verbose", action='store_true', help='verbose mode')
    parser.add_argument("-d", "--debug", action='store_true', help='debug mode')
    parser.add_argument("--dry", action='store_true', help='dry run')
    parser.add_argument("--infomap", action='store_true', help='show ID to infohash map')
    parser.add_argument("--pieces", type=str, metavar='INFO-HASH', help='get pieces info')
    parser.add_argument("--bitfield", type=str, metavar='INFO-HASH', help='get bitfield info')
    parser.add_argument("--files", type=str, metavar='INFO-HASH', help='get files info')
    parser.add_argument("--files-xml", type=str, metavar='INFO-HASH', help='get files info (XML)')
    parser.add_argument("--aria2", type=str, metavar='INFO-HASH', help='generate aria2 script for downloading')
    parser.add_argument("--aria2-options", type=str, metavar='OPTIONS', help='options to pass to aria2c')
    #parser.add_argument("--dummy-data", type=str, metavar='FILE', help='use dummy XML data')
    
    args = parser.parse_args()
    #print args
    #sys.exit()
    
    jsi = JustSeedIt();
    
    if args.debug:
        jsi.debug = 1
        
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
        
    elif args.list_xml:
        print jsi.list_xml()
        
    elif args.info:
        jsi.info(args.info);
 
    elif args.infomap:
        jsi.info_map();

    elif args.pieces:
        print jsi.pieces(args.pieces);
 
    elif args.bitfield:
        print jsi.bitfield(args.bitfield);
 
    elif args.files:
        print jsi.files(args.files);

    elif args.files_xml:
        print jsi.files(args.files_xml);
                              
    elif args.download_links:
        urls = jsi.download_links(args.download_links);
        for line in urls:
            print line
 
    elif args.aria2:
        jsi.aria2_script(args.aria2)
        
                               
    else:
        print "Invalid action"
        
    if args.pause:
        raw_input("Press Enter to continue...")
        
    sys.exit()
   
