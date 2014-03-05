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
import urllib, urllib2, xmltodict, json, argparse, poster

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
        
class JustSeedIt():
    
    api_key = "";
    url = "https://api.justseed.it"
    
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

            #if self.debug:
            #    print headers
            
            req = urllib2.Request(self.url + page, post_data, headers)
            
            response = urllib2.urlopen(req)
            xml_response = response.read()
            self.xml_response = xml_response

        except urllib2.URLError, urllib2.HTTPError:
            print "URL or HTTP error"
            sys.exit()
        
        if self.check_server_response(xml_response):
            self.error = False
            if self.debug:
                print xml_response
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
       
    def add_magnet(self,magnet):
        print "Adding magnet link with ratio {}".format(self.ratio)
        
        response_xml = self.api("/torrent/add.csp",{'maximum_ratio':str(self.ratio), 'url': magnet })
        #response_xml = self.api("/torrent/add.csp",{'maximum_ratio':"3", 'url': magnet })
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

    def list(self):
        """ Show torrents in pretty format
        """
        
        print "Getting list of torrents..."
        
        #xml_response = self.xml_from_file("list.xml")
        xml_response = self.api("/torrents/list.csp")
        if xml_response:
            result = xmltodict.parse(xml_response)
            torrents = result['result']['data']['row']
            for torrent in torrents:
                print  urllib.unquote(torrent['name'])
                
                if float(torrent['downloaded_as_bytes']) == 0:
                    ratio = 0.0
                else:
                    ratio = float(torrent['uploaded_as_bytes']) / float(torrent['downloaded_as_bytes'])
                #print ratio
                
                print "{:>12} {:>8} {:>12} {:>.2f}".format(torrent['size_as_string'],
                                                          torrent['percentage'] + "%",
                                                          torrent['elapsed_as_string'],
                                                          ratio)
                #print json.dumps(result['result']['data'], indent=4)

    
if __name__ == "__main__":
    
    # Set up CLI arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("--magnet", "-m", help="magnet link", type=str, nargs=1)
    parser.add_argument("--torrent-file", "-t", type=str, help='add single torrent file')
    parser.add_argument("--list", "-l", action='store_true', help='list torrents')
    parser.add_argument("--list-xml", action='store_true', help='list torrents in raw XML format')
    parser.add_argument("--download-links", type=str, help='get download links')
    parser.add_argument("--pause", "-p", action='store_true', help='pause when finished')
    parser.add_argument("--ratio", "-r", type=float, help='set ratio')
    parser.add_argument("--verbose", "-v", action='store_true', help='verbose mode')
    parser.add_argument("--debug", "-d", action='store_true', help='debug mode')
        
    args = parser.parse_args()
    
    jsi = JustSeedIt();
    
    if args.debug:
        jsi.debug = True
 
    if args.verbose:
        jsi.verbose = True
        
    if args.ratio:
        jsi.ratio = args.ratio
    
    if args.magnet:
        jsi.add_magnet(args.magnet[0])
        
    elif args.torrent_file:
        jsi.add_torrent_file(args.torrent_file)
        
    elif args.list:
        jsi.list()
        
    elif args.list_xml:
        print jsi.list_xml()
        
    else:
        print "Invalid action"
        
    if args.pause:
        raw_input("Press Enter to continue...")
        
    sys.exit()
   
