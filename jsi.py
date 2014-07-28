#!/usr/bin/env python
"""

jsi.py

Unofficial justseed.it cli client

---

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

"""

JSI_VERSION = "0.0"

import sys
import os
import urllib
import urllib2
import json
import argparse
import poster
import collections
import re
import StringIO
import gzip
import bencode
import math
from colorama import init, Fore, Back, Style
from xml.dom import minidom
from datetime import datetime
import platform
import glob
import csv
import io


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
        

def sizeof_fmt(num):
    for x in ['B' ,'KB' ,'MB' ,'GB' ,'TB']:
        if num < 1024.0:
            return "%3.1f %s" % (num, x)
        num /= 1024.0


class JustSeedIt():
    
    # Default options

    if os.getenv('JSI_OUTPUT_DIR'):
        DEFAULT_DOWNLOAD_DIR = os.getenv('JSI_OUTPUT_DIR')
        # add trailing slash, if not given
        if DEFAULT_DOWNLOAD_DIR[-1:] != '/':
            DEFAULT_DOWNLOAD_DIR += '/'
    else:
        DEFAULT_DOWNLOAD_DIR = 'd:/Downloads/justseed.it Downloads/'

    if os.getenv('JSI_RATIO'):
        DEFAULT_RATIO = os.getenv('JSI_RATIO')
    else:
        DEFAULT_RATIO = 1.0

    if os.getenv('JSI_ARIA2_OPTIONS'):
        DEFAULT_ARIA2_OPTIONS = os.getenv('JSI_ARIA2_OPTIONS')
    else:
        DEFAULT_ARIA2_OPTIONS = "--file-allocation=none --check-certificate=false --max-concurrent-downloads=8 " + \
            "--continue --max-connection-per-server=8 --min-split-size=1M"

    DEFAULT_API_SERVER = "https://api.justseed.it"

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
        self.error = False
        self.debug = 0
        self.dry_run = 0
        self.aria2_log = False
        self.xml_mode = False
        self.file_data = None
        self.compress = True
        self.verbose = False
        self.xml_response = ''  # filled with results every time an api call is made
        self.id_to_infohash_map = {}  # map id number to infohash
        self.infohash_to_name = {}  # map infohas to torrent name
        self.torrents = None  # filled when self.list_update() is called
        self.data_remaining_as_bytes = 0  # remaining quota
        self.data_remaining_as_string = 0  # remaining quota

        self.debug_logfile = 'debug.log'
        self.aria2_logfile = 'aria2.log'

        self.file_attr = []

        # List modifiers
        self.list_complete_only = False
        self.list_incomplete_only = False
        self.list_stopped_only = False
        self.list_transfer_only = False

        # Values used in --edit operations
        self.edit_opts = []
        self.ratio = self.DEFAULT_RATIO  # this is also used in add, --torrent
        self.name = None
        self.add_tracker_url = ''
        self.delete_tracker_url = ''
        self.label = ''

        if platform.system() == "Windows":
            self._globbing = True
        else:
            self._globbing = False

    @staticmethod
    def pretty_print(d):
        print(json.dumps(d, indent=4))

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

    def debug_log(self, data, marker=None):
        f = open(self.debug_logfile, 'a')
        if marker:
            datestr = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write("\n[{} -- {}]\n".format(datestr, marker))
        if data != '':
            f.write(data + "\n")
        f.close()
        return

    def api(self, page, post_data=None):
        """ Make a API call using multipart/form-data POST
            Returns XML response on success or False on error
        """
        if not post_data:
            post_data = {}
        post_data['api_key'] = self.api_key
        
        if self.debug:
            self.debug_log("Calling {:} with:".format(page), "API CALL")
            for key, value in post_data.items():
                if key == 'torrent_file':
                    # don't dump torrent file data into log file
                    self.debug_log("{:>15}: {:}".format(key, "[binary data]"))
                else:
                    self.debug_log("{:>15}: {:}".format(key, value))
        
        try:
            # for application/x-www-form-urlencoded
            #post_data = urllib.urlencode( data ) 
            #req = urllib2.Request(self.url + page, post_data)
            
            # for multipart/form-data
            poster.streaminghttp.register_openers()
            post_data, headers = poster.encode.multipart_encode(post_data)

            if self.dry_run:
                print "\nHeaders:\n"
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

            if self.debug:
                self.debug_log("", "XML RESPONSE")
                self.debug_log(xml_response)

        except urllib2.URLError, urllib2.HTTPError:
            sys.stderr.write("Error: URL or HTTP error, server did not respond. Quitting\n")
            sys.exit()
        
        if self.check_server_response(xml_response):
            # Server responded with "SUCCESS"
            self.error = False
            return xml_response
        else:
            # Server did NOT respond with "SUCCESS"
            # self.check_server_response() will already display an error message
            self.error = True
            sys.stderr.write("API server did not respond with SUCCESS on last call. Quitting.")
            #sys.exit()
            #print xml_response
            return False # do not quit, just skip this call and try next one

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
        """ Find the info hash, when given a ID, returns info hash
        """
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
        """ Grab info about a (single) torrent. Returns XML response
        """
        if len(infohash) != 40:
            infohash = self.id_to_infohash(infohash)
            if not infohash:
                return
            
        xml_response = self.api("/torrent/information.csp", {'info_hash': infohash})
        if self.xml_mode:
            print xml_response
            sys.exit()

        xml = minidom.parseString(xml_response)
        for element in xml.getElementsByTagName('data')[0].childNodes:
            if element.nodeType == element.ELEMENT_NODE:
                key = element.nodeName
                try:
                    value = xml.getElementsByTagName(element.nodeName)[0].firstChild.nodeValue
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
        """ Display pieces for given info hashes or IDs, returns XML response
        """
        if len(infohash) != 40:
            infohash = self.id_to_infohash(infohash)
            if not infohash:
                return            

        response_xml = self.api("/torrent/pieces.csp", {'info_hash': infohash})
        
        if self.xml_mode:
            print response_xml
            sys.exit()

        return response_xml

    def pieces_aria2(self, infohash):
        # get pieces info
        self.pieces(infohash)
        pieces = minidom.parseString(self.xml_response).getElementsByTagName("row")

        for piece in pieces:
            # get useful info / metadata for each piece
            piece_number = piece.getElementsByTagName('number')[0].firstChild.nodeValue
            piece_hash = piece.getElementsByTagName('hash')[0].firstChild.nodeValue
            piece_size = piece.getElementsByTagName('size')[0].firstChild.nodeValue
            piece_url = urllib.unquote(piece.getElementsByTagName('url')[0].firstChild.nodeValue) + "&api_key=" + self.api_key

            print "aria2c {} -o piece.{} \"{}\"".format(self.aria2_options, piece_number, piece_url)

            # Note: use should perform sha1sum check on each piece

    def pieces_sha1sum(self, infohash):
        # get pieces info, generate sha1sum output, user uses this to redirect to a sha1sum files
        # ... > pieces.sha1
        self.pieces(infohash)
        pieces = minidom.parseString(self.xml_response).getElementsByTagName("row")

        for piece in pieces:
            # get useful info / metadata for each piece
            piece_number = piece.getElementsByTagName('number')[0].firstChild.nodeValue
            piece_hash = piece.getElementsByTagName('hash')[0].firstChild.nodeValue
            piece_size = piece.getElementsByTagName('size')[0].firstChild.nodeValue
            piece_url = urllib.unquote(piece.getElementsByTagName('url')[0].firstChild.nodeValue) + "&api_key=" + self.api_key

            print "{} *pieces.{}".format(piece_hash, piece_number)

    def bitfield(self, infohash):
        """ Display bitfield for given info hashes or IDs, returns XML response
        """
        if len(infohash) != 40:
            infohash = self.id_to_infohash(infohash)
            if not infohash:
                return
                        
        response_xml = self.api("/torrent/bitfield.csp", {'info_hash': infohash})

        if self.xml_mode:
            print response_xml
            sys.exit()

        number_of_pieces = int(minidom.parseString(self.xml_response).getElementsByTagName('pieces')[0].firstChild.nodeValue)
        bitfield_as_string = minidom.parseString(self.xml_response).getElementsByTagName('bitfield')[0].firstChild.nodeValue

        # generate bitfield as an array
        bitfield = []
        for bit in bitfield_as_string:
            if bit == '1':
                bitfield.append(1)
            elif bit == '0':
                bitfield.append(0)
            else:
                sys.stderr.write("Detected invalid bitfield char, expected '0' or '1' but got '{}'".format(bit))
                sys.exit()

        if len(bitfield) != number_of_pieces:
            sys.stderr.write("Number of elements in bitfield does not match number of pieces {} != {}".format(len(bitfield),number_of_pieces))
            sys.exit()

        self.bitfield_array = bitfield

        #print "Bitfield for " + Style.BRIGHT + "{}".format(infohash) + Style.RESET_ALL
        #print "  Pieces: " + str(number_of_pieces)
        #print "  Bitfield: " + bitfield_as_string
        return response_xml


    def trackers(self, infohash):
        """ Display list of trackers for given info hashes or IDs, returns XML response
        """
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
        """ Edit torrent. Can change ratio or name. Does not return anything.
        """
        
        parameters = self.edit_opts
        
        self.list_update()
        
        if not isinstance(infohashes, list):
            infohashes = [infohashes]

        infohashes = self.expand(infohashes)

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
                if torrent_id:
                    sys.stderr.write("Changing name of torrent {} to \"{}\"\n".format(torrent_id, self.name))
                else:
                    sys.stderr.write("Changing name of torrent {} to \"{}\"\n".format(infohash, self.name))

                if self.name != "":
                    response_xml = self.api("/torrent/set_name.csp",
                                            {'info_hash': infohash, 'name': self.name})
                else:
                    sys.stderr.write("Resetting torrent name to default.\n")
                    response_xml = self.api("/torrent/set_name.csp",
                                            {'info_hash': infohash})
                if self.xml_mode:
                    print response_xml

            if 'add_tracker' in parameters:
                # add tracker url
                if torrent_id:
                    sys.stderr.write("Adding tracker \"{}\" to torrent {}\n".format(self.add_tracker_url, torrent_id))
                else:
                    sys.stderr.write("Adding tracker \"{}\" to torrent {}\n".format(self.add_tracker_url, infohash))

                if self.add_tracker_url != "":
                    response_xml = self.api("/torrent/add_tracker.csp",
                                            {'info_hash': infohash, 'url': self.add_tracker_url})

                if self.xml_mode:
                    print response_xml

            if 'delete_tracker' in parameters:
                # delete tracker url
                if torrent_id:
                    sys.stderr.write("Deleting tracker \"{}\" from torrent {}\n".format(self.delete_tracker_url, torrent_id))
                else:
                    sys.stderr.write("Deleting tracker \"{}\" from torrent {}\n".format(self.delete_tracker_url, infohash))

                if self.add_tracker_url != "":
                    response_xml = self.api("/torrent/delete_tracker.csp",
                                            {'info_hash': infohash, 'url': self.add_tracker_url})

                if self.xml_mode:
                    print response_xml

            if 'label' in parameters:
                # edit label of torrent
                if torrent_id:
                    sys.stderr.write("Adding label \"{}\" to torrent {}\n".format(self.label, torrent_id))
                else:
                    sys.stderr.write("Adding label \"{}\" to torrent {}\n".format(self.label, infohash))

                if self.add_tracker_url != "":
                    response_xml = self.api("/torrent/label.csp",
                                            {'info_hash': infohash, 'url': self.label})
                else:
                    # remove label
                    response_xml = self.api("/torrent/label.csp",
                                            {'info_hash': infohash})

                if self.xml_mode:
                    print response_xml

        if self.xml_mode:
            sys.exit()
            
        return

    def peers(self, infohash):
        """ Display list of peers, returns XML response.
            Currently not implemented.
        """

        if len(infohash) != 40:
            infohash = self.id_to_infohash(infohash)
            if not infohash:
                return
                       
        response_xml = self.api("/torrent/peers.csp", {'info_hash': infohash})

        if self.xml_mode:
            print response_xml
            sys.exit()

        return response_xml

    def reset(self, infohashes):
        """ Reset downloaded, uploaded, ratio counter for torrent(s)
        """

        self.list_update()

        infohashes = self.expand(infohashes)

        for infohash in infohashes:
            torrent_id = infohash
            if len(infohash) != 40:
                infohash = self.id_to_infohash(infohash)
                if not infohash:
                    continue

            sys.stderr.write("Resetting torrent: {}\n".format(torrent_id))

            response_xml = self.api("/torrent/reset.csp", {'info_hash': infohash})

            if self.xml_mode:
                print response_xml
                continue

        return

    def start(self, infohashes):
        """ Start torrent(s)
        """

        self.list_update()

        infohashes = self.expand(infohashes)

        for infohash in infohashes:
            torrent_id = infohash
            if len(infohash) != 40:
                infohash = self.id_to_infohash(infohash)
                if not infohash:
                    continue

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

        infohashes = self.expand(infohashes)

        for infohash in infohashes:
            torrent_id = infohash
            if len(infohash) != 40:
                infohash = self.id_to_infohash(infohash)
                if not infohash:
                    continue
            
            sys.stderr.write("Stopping torrent: {}\n".format(torrent_id))

            response_xml = self.api("/torrent/stop.csp", {'info_hash': infohash})

            if self.xml_mode:
                print response_xml
                continue

        return

    def delete(self, infohashes):
        """ Delete torrent(s)
        """

        self.list_update()

        infohashes = self.expand(infohashes)

        for infohash in infohashes:
            torrent_id = infohash
            if len(infohash) != 40:
                infohash = self.id_to_infohash(infohash)
                if not infohash:
                    continue

            sys.stderr.write("Deleting torrent: {}\n".format(torrent_id))

            response_xml = self.api("/torrent/delete.csp", {'info_hash': infohash})

            if self.xml_mode:
                print response_xml
                continue

        return

    def delete_stopped(self):
        """ Delete all torrents in a stopped state
        """
        #self.list_stopped_only = True

        stopped_torrents = []

        self.list_update()
        for torrent in self.torrents:
            #self.pretty_print(torrent)

            if torrent.getElementsByTagName('status')[0].firstChild.nodeValue != "stopped":
                # skip anything that is not stopped
                continue

            # Make list of stopped torrents, we'll come back to this later
            stopped_torrents.append(torrent)

        # From out list of stopped torrents, delete each one
        for torrent in stopped_torrents:
            sys.stderr.write("Deleting {} {}\n".format(Fore.RED + torrent.getAttribute('id') + Fore.RESET, torrent.getElementsByTagName('name')[0].firstChild.nodeValue))
            torrent_hash = torrent.getElementsByTagName('info_hash')[0].firstChild.nodeValue
            self.delete(torrent_hash)

        return

    def download_links_renew(self, infohashes):
        """ Regenerate download links for torrent
        """

        self.list_update()

        infohashes = self.expand(infohashes)

        for infohash in infohashes:
            torrent_id = infohash
            if len(infohash) != 40:
                infohash = self.id_to_infohash(infohash)
                if not infohash:
                    continue

            sys.stderr.write("Renewing links for torrent: {}\n".format(torrent_id))

            response_xml = self.api("/torrent/links/create.csp", {'info_hash': infohash, 'force': 1})

            if self.xml_mode:
                print response_xml
                continue

        return

    def files(self, infohash):
        if len(infohash) != 40:
            infohash = self.id_to_infohash(infohash)
            if not infohash:
                return

        self.bitfield(infohash)  # check bitfield for piece information

        response_xml = self.api("/torrent/files.csp", {'info_hash': infohash})

        if self.xml_mode:
            print response_xml
            sys.exit()


        rows = minidom.parseString(self.xml_response).getElementsByTagName("row")
        #sys.stderr.write("Number of files: " + str(len(rows)) + "\n")

        for row in rows:
            try:
                url = urllib.unquote(row.getElementsByTagName('url')[0].firstChild.nodeValue)
            except AttributeError:
                url = ""

            # check whether individual files are completed or not, byt referencing against bitfield
            start_piece = int(row.getElementsByTagName('start_piece')[0].firstChild.nodeValue)
            end_piece = int(row.getElementsByTagName('end_piece')[0].firstChild.nodeValue)
            pieces_complete = 1
            for p in range(start_piece, end_piece):
                if jsi.bitfield_array[p] != 1:
                    pieces_complete = 0

            data = (
                row.getElementsByTagName('torrent_offset')[0].firstChild.nodeValue,
                row.getElementsByTagName('start_piece')[0].firstChild.nodeValue,
                row.getElementsByTagName('start_piece_offset')[0].firstChild.nodeValue,
                row.getElementsByTagName('end_piece')[0].firstChild.nodeValue,
                row.getElementsByTagName('end_piece_offset')[0].firstChild.nodeValue,
                urllib.unquote(row.getElementsByTagName('path')[0].firstChild.nodeValue),
                row.getElementsByTagName('size_as_bytes')[0].firstChild.nodeValue,
                row.getElementsByTagName('total_downloaded_as_bytes')[0].firstChild.nodeValue,
                url,
                str(pieces_complete)
            )

            # store it internally too
            jsi.file_attr.append(data)

        return response_xml

    def files_csv(self, infohash=None):
        # Displayed detailed csv on file information
        if infohash:
            self.files(infohash)

        writer = csv.writer(sys.stdout, dialect='excel')

        #csvout = io.StringIO()
        #writer = csv.writer(csvout, dialect='excel')

        # write heading
        writer.writerow([
            'torrent_offset',
            'start_piece',
            'start_piece_offset',
            'end_piece',
            'end_piece_offset',
            'path',
            'size_as_bytes',
            'total_downloaded_as_bytes',
            'url',
            'piece_complete'  # is the piece complete? 0 or 1
        ])

        # extra blank lines written to stdout on Windows, need to fix!
        # can fix by opening stdout as "wb", but not sure if this is possible?

        for file in jsi.file_attr:
            writer.writerow(file)

        #print csvout.getvalue()

    def files_pretty(self, infohash):
        # Display pretty coloured file info (file path, name and sizes
        if infohash:
            self.files(infohash)

        for file in jsi.file_attr:
            # must use index numbers, see self.files_csv for positions
            # all fields are string
            if file[9] == "1":
                # file complete
                print "{} {}".format(file[5], Fore.GREEN + file[6] + Fore.RESET)
            else:
                # file incomplete
                print "{} {}".format(file[5], Fore.RED + int(file[6]) + Fore.RESET)

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

        infohashes = self.expand(infohashes)

        for infohash in infohashes:
            if len(infohash) != 40:
                infohash = self.id_to_infohash(infohash)
                if not infohash:
                    continue

            self.api("/torrent/files.csp", {'info_hash': infohash})
            if self.xml_mode:
                print self.xml_response
                continue

            downloads = minidom.parseString(self.xml_response).getElementsByTagName("row")
            self.file_data = downloads
            for download in downloads:
                try:
                    url_list.append(urllib.unquote(download.getElementsByTagName('url')[0].firstChild.nodeValue))
                except AttributeError:
                    # No download link for this file
                    pass

        if self.xml_mode:
            sys.exit()

        return url_list

    @staticmethod
    def expand(original):
        """ Expands ['5..8'] to ['5','6','7','8']
        """
        if not isinstance(original, list):
            original = [original]
        if len(original) == 1:
            result = re.match("([0-9]+)\.\.([0-9]+)", original[0])

            if result:
                matched = result.groups()
                if len(matched) == 2:
                    output = []
                    for n in range(int(matched[0]), int(matched[1])+1):
                        output.append(str(n))
                    return output
                else:
                    return original
            else:
                return original
        else:
            # no change
            return original

    def aria2_script(self, infohashes, options=None):
        """ Generate a aria2 download script for selected infohash or id number
        """
        infohashes = self.expand(infohashes)

        self.list_update()

        # grab *all* download links
        xml_download_links_all = self.api("/links/list.csp")

        for infohash in infohashes:
            # get info hash

            if len(infohash) != 40:
                torrent_id = infohash
                infohash = self.id_to_infohash(infohash)
                if not infohash:
                    continue
            else:
                torrent_id = infohash

            # loop through each row of link list output
            link_rows = minidom.parseString(jsi.xml_response).getElementsByTagName("row")
            for row in link_rows:

                link_infohash = row.getElementsByTagName('info_hash')[0].firstChild.nodeValue

                # check for missing infohash
                if link_infohash == infohash:

                    # found a matching file for the selected infohash
                    filename = row.getElementsByTagName('file_name')[0].firstChild.nodeValue  # not used
                    url = self.urldecode_to_ascii(row.getElementsByTagName('url')[0].firstChild.nodeValue)

                    # get torrent name
                    name = self.infohash_to_name[infohash]

                    # prepare aria2 command line
                    aria2_options = self.aria2_options
                    file_path = self.urldecode_to_ascii(re.sub('https://download.justseed\.it/.{40}/', '', url))
                    subdir_name = os.path.dirname(file_path)
                    file_name = os.path.basename(file_path)
                    output_dir = self.output_dir + subdir_name

                    if self.aria2_log:
                        aria2_options = aria2_options + " --log=\"" + self.aria2_logfile + "\" --log-level=notice"

                    print "aria2c {} -d \"{}\" -o \"{}\" \"{}\"".format(aria2_options, output_dir, file_name, url)

            continue  # go to next infohash

        return

    #def info_map(self):
    #    self.list_update()
    #    print " ID INFOHASH"
    #    for torrent_id, torrent in self.torrents.items():
    #        print "{:>3} {}".format(torrent_id, torrent['info_hash'])

    @staticmethod
    def glob_expand(arguments):
        """ On Windows console, it does not glob *.torrent - so lets do it manually
        """
        globbed_list = []
        for item in arguments:
            items = glob.glob(item)
            if len(items) == 0:
                sys.stderr.write("Could not find file '{0}'".format(item))
                continue
            for x in items:
                globbed_list.append(x)
        return globbed_list

    def add_magnet(self, magnets):
        """ Add magnet links defined in list 'magnets'.
            Doesn't return anything
        """
        
        # if argument is single line string, turn it into a single element list
        if isinstance(magnets,str):
            single_magnet = magnets
            magnets = []
            magnets.append(single_magnet)
            
        for magnet in magnets:
            sys.stderr.write("Adding magnet link \"{}\" with ratio {}\n".format(magnet, self.ratio))
            
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

        if self._globbing:
            # We need to manually glob
            filenames = self.glob_expand(filenames)

        for filename in filenames:
        
            sys.stderr.write("Adding torrent file '{}' with ratio {}\n".format(filename, self.ratio))
            
            try:
                f = open(filename, 'rb')
                torrent_data = f.read()
            except IOError:
                sys.stderr.write("Could not open file '{0}'".format(filename))
                continue
    
            # Check .torrent file data is valid
            try:
                bencode.bdecode(torrent_data)
            except bencode.BTFailure:
                sys.stderr.write("Error: Ignoring '{}', not a valid .torrent file!\n".format(filename))
                continue
            
            self.api("/torrent/add.csp", {'torrent_file': torrent_data, 'maximum_ratio': str(self.ratio)})

            if self.xml_mode:
                print self.xml_response
                continue
        
        return

    def add_infohash(self, infohashes):
        """ Add torrents to system, referenced by infohash
            Doesn't return anything.
        """

        for infohash in infohashes:

            sys.stderr.write("Adding infohash '{}' with ratio {}\n".format(infohash, self.ratio))

            # Check infohash is valid string (40 char hexadecimal string)
            match = re.search("^[0-9A-Fa-f]{40}$", infohash)
            if not match:
                sys.stderr.write("Not a valid hash! Skipping \"{}\"...".format(infohash))
                continue

            self.api("/torrent/add.csp", {'info_hash': infohash, 'maximum_ratio': str(self.ratio)})

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
        
            # Make new map
            self.id_to_infohash_map = collections.OrderedDict()

            # Get all torrent data in xml format
            self.torrents = minidom.parseString(xml_response).getElementsByTagName("row")

            for torrent in self.torrents:
                # Each torrent

                self.id_to_infohash_map[torrent.getAttribute('id')] = torrent.getElementsByTagName('info_hash')[0].firstChild.nodeValue
                self.infohash_to_name[torrent.getElementsByTagName('info_hash')[0].firstChild.nodeValue] = torrent.getElementsByTagName('name')[0].firstChild.nodeValue

            self.data_remaining_as_bytes = minidom.parseString(xml_response).getElementsByTagName("data_remaining_as_bytes")[0].firstChild.nodeValue
            self.data_remaining_as_string = minidom.parseString(xml_response).getElementsByTagName("data_remaining_as_string")[0].firstChild.nodeValue

        else:
            # list already up to date
            # don't need to do anything
            pass
        
        return self.xml_response

    def list_links(self):
        xml_response = self.api("/links/list.csp")
        if not xml_response:
            return

        return self.xml_response


    def list(self):
        """ Show torrents in pretty format
        """
        xml_response = self.list_update()
        if self.xml_mode:
            print xml_response
            sys.exit()

        # count all listed downloads and uploads
        total_downloaded = 0
        total_uploaded = 0

        # count total bandwidth current being used
        total_rate_in = 0
        total_rate_out = 0

        # count number of items listed
        list_count = 0

        for torrent in self.torrents:

            # 'name' is a urlencoded UTF-8 string
            # clean this up, many consoles can't display UTF-8, so lets replace unknown chars
            name = self.urldecode_to_ascii(torrent.getElementsByTagName('name')[0].firstChild.nodeValue)
            torrent_id = torrent.getAttribute("id")

            if self.list_incomplete_only:
                if torrent.getElementsByTagName('percentage_as_decimal')[0].firstChild.nodeValue == "100.0":
                    # skip completed torrents
                    continue

            if self.list_complete_only:
                if torrent.getElementsByTagName('percentage_as_decimal')[0].firstChild.nodeValue != "100.0":
                    # skip completed torrents
                    continue

            if self.list_transfer_only:
                if int(torrent.getElementsByTagName('data_rate_in_as_bytes')[0].firstChild.nodeValue) == 0 and \
                    int(torrent.getElementsByTagName('data_rate_out_as_bytes')[0].firstChild.nodeValue) == 0:
                    continue

            if self.list_stopped_only:
                if torrent.getElementsByTagName('status')[0].firstChild.nodeValue != "stopped":
                    # skip anything that is not stopped
                    continue

            # Print torrent name
            print Fore.CYAN + "[" + Fore.RESET + Style.BRIGHT + "{:>3}".format(torrent_id) +\
                Style.RESET_ALL + Fore.CYAN + "] {}".format(name) + Fore.RESET
            
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

            total_downloaded += int(torrent.getElementsByTagName('downloaded_as_bytes')[0].firstChild.nodeValue)
            total_uploaded += int(torrent.getElementsByTagName('uploaded_as_bytes')[0].firstChild.nodeValue)

            total_rate_in += int(torrent.getElementsByTagName('data_rate_in_as_bytes')[0].firstChild.nodeValue)
            total_rate_out += int(torrent.getElementsByTagName('data_rate_out_as_bytes')[0].firstChild.nodeValue)

            # ammend in/out rate to status string
            rate_in = int(torrent.getElementsByTagName('data_rate_in_as_bytes')[0].firstChild.nodeValue)
            rate_out = int(torrent.getElementsByTagName('data_rate_out_as_bytes')[0].firstChild.nodeValue)

            if math.floor(int(rate_in)):
                status += " IN:"+Fore.RED+"{}".format(int(rate_in)/1024)+Fore.RESET+"K"
            if math.floor(int(rate_out)):
                status += " OUT:"+Fore.RED+"{}".format(int(rate_out)/1024)+Fore.RESET+"K"

            #if math.floor(int(rate_in)):
            #    status += " IN:"+Fore.RED+"{}".format(int(rate_in))+Fore.RESET
            #if math.floor(int(rate_out)):
            #    status += " OUT:"+Fore.RED+"{}".format(int(rate_out))+Fore.RESET

            print "{:>13} {:>8} {:>12} {:.2f} {:5.2f} {}".format(torrent.getElementsByTagName('size_as_string')[0].firstChild.nodeValue,
                                                                 torrent.getElementsByTagName('percentage_as_decimal')[0].firstChild.nodeValue + "%",
                                                                 torrent.getElementsByTagName('elapsed_as_string')[0].firstChild.nodeValue,
                                                                 ratio,
                                                                 float(torrent.getElementsByTagName('maximum_ratio_as_decimal')[0].firstChild.nodeValue),
                                                                 status)

            list_count += 1
        
        print ""
        print "Listed " + Fore.RED + "{}".format(list_count) + Fore.RESET + " torrents"
        print "Downloaded: " + Fore.RED + "{}".format(sizeof_fmt(total_downloaded)) + Fore.RESET +\
            " Uploaded: " + Fore.RED + "{}".format(sizeof_fmt(total_uploaded)) + Fore.RESET
        print "Download rate: " + Fore.RED + "{}/s".format(sizeof_fmt(total_rate_in)) + Fore.RESET +\
            " Upload rate: " + Fore.RED + "{}/s".format(sizeof_fmt(total_rate_out)) + Fore.RESET
        print "Quota remaining: " + Fore.RED + "{}".format(sizeof_fmt(int(self.data_remaining_as_bytes))) + Fore.RESET

        return
    
if __name__ == "__main__":
    # Set up CLI arguments
    parser = argparse.ArgumentParser(prog='jsi.py', description='justseed.it cli client, version ' + JSI_VERSION, epilog='When INFO-HASH is asked as a parameter, a torrent ID may also be used. This corresponding ID number is shown in the first column of the --list output.')

    parser.add_argument("--add-tracker", type=str, metavar='TRACKER-URL', help='add tracker (use together with -e)')
    parser.add_argument("--aria2", type=str, nargs='*', metavar='INFO-HASH', help='generate aria2 script for downloading files')
    parser.add_argument("--aria2-options", type=str, metavar='OPTIONS', help='options to pass to aria2c (default: "{}")'.format(JustSeedIt.DEFAULT_ARIA2_OPTIONS))
    parser.add_argument("--aria2-log", action='store_true', help='log aria2 messages to aria2.log, used with --aria2')
    parser.add_argument("--api-key", type=str, metavar='APIKEY', help='specify 40-char api key')
    parser.add_argument("--bitfield", type=str, metavar='INFO-HASH', help='get bitfield info')
    parser.add_argument("--debug", action='store_true', help='debug mode, write log file to debug.log')
    parser.add_argument("--delete-tracker", type=str, metavar='TRACKER-URL', help='delete tracker (use together with -e)')
    parser.add_argument("--delete", type=str, nargs='*', metavar='INFO-HASH', help='delete torrent')
    parser.add_argument("--delete-stopped", action='store_true', help='delete all torrents in a stopped state')
    parser.add_argument("--download-links", "--dl", type=str, nargs='*', metavar='INFO-HASH', help='get download links')
    parser.add_argument("--download-links-renew", type=str, metavar='INFO-HASH', help='generate all new download links')
    parser.add_argument("--dry", action='store_true', help='dry run')
    parser.add_argument("-e", "--edit", type=str, nargs='*', metavar='INFO-HASH', help='edit torrent, use with --ratio, --name, --add-tracker or --delete-tracker')
    parser.add_argument("--files", type=str, metavar='INFO-HASH', help='display file names and sizes')
    parser.add_argument("--files-csv", type=str, metavar='INFO-HASH', help='display detailed file information in csv format')
    parser.add_argument("-i", "--info", type=str, metavar='INFO-HASH', help='show info for torrent')
    parser.add_argument("--infohash", type=str, nargs='*', metavar='INFO-HASH', help='add torrent by infohash')
    #parser.add_argument("--infomap", action='store_true', help='show ID to infohash map')
    parser.add_argument("--label", type=str, metavar='LABEL', help='edit labelm set to "" to remove label')
    parser.add_argument("-l", "--list", action='store_true', help='list torrents')
    parser.add_argument("--list-complete", action='store_true', help='list only complete torrents')
    parser.add_argument("--list-incomplete", action='store_true', help='list only incomplete torrents')
    parser.add_argument("--list-links", action='store_true', help='list all download links, xml format')
    parser.add_argument("--list-stopped", action='store_true', help='list only stopped torrents')
    parser.add_argument("--list-transfer", action='store_true', help='list only torrents with data transfer in progress')
    parser.add_argument("--list-tags", action='store_true', help=argparse.SUPPRESS)
    parser.add_argument("--list-variables", action='store_true', help=argparse.SUPPRESS)
    parser.add_argument("-m", "--magnet", type=str, nargs='*', help="add torrent using magnet link", metavar='MAGNET-TEXT')
    parser.add_argument("--name", type=str, help='set name (used with -e), set as a empty string "" to reset to default name')
    parser.add_argument("--no-compress", action='store_true', help='request api server to not use gzip encoding')
    parser.add_argument("-o", "--output-dir", type=str, help='set output dir for aria2 scripts, always use a trailing slash (default: "{}")'.format(JustSeedIt.DEFAULT_DOWNLOAD_DIR))
    parser.add_argument("-p", "--pause", action='store_true', help='pause when finished')
    parser.add_argument("--peers", type=str, metavar='INFO-HASH', help='get peers info')
    parser.add_argument("--pieces", type=str, metavar='INFO-HASH', help='get pieces info')
    parser.add_argument("--pieces-aria2", type=str, metavar='INFO-HASH', help='generate aria2 script to download completed pieces')
    parser.add_argument("--pieces-sha1sum", type=str, metavar='INFO-HASH', help='generate sha1sums of individual pieces')
    parser.add_argument("--reset", type=str, metavar='INFO-HASH', help='reset downloaded and uploaded counter for torrent, will also reset the ratio')
    parser.add_argument("-t", "--torrent-file", type=str, nargs='*', metavar='TORRENT-FILE', help='add torrent with .torrent file')
    parser.add_argument("--trackers", type=str, metavar='INFO-HASH', help='get trackers info')
    parser.add_argument("-r", "--ratio", type=float, help='set maximum ratio, used in conjunction with -t, -m or -e (default: {})'.format(str(JustSeedIt.DEFAULT_RATIO)))
    parser.add_argument("--start", type=str, nargs='*', metavar='INFO-HASH', help='start torrent')
    parser.add_argument("--stop", type=str, nargs='*', metavar='INFO-HASH', help='stop torrent')
    parser.add_argument("-v", "--verbose", action='store_true', help='verbose mode')
    parser.add_argument("--version", action='store_true', help='display version number')
    parser.add_argument("--xml", action='store_true', help='display result as XML')
    parser.add_argument("-z", "--compress", action='store_true', help='request api server to use gzip encoding (default: True)')

    # set up coloring with colorama
    terminal = os.getenv('TERM')
    if terminal == 'rxvt' or terminal == 'xterm':
        # Cygwin, xterm emulators
        init(autoreset=True, convert=False, strip=False)
    else:
        # Standard windows console
        init(autoreset=True)

    args = parser.parse_args()

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

    if args.no_compress:
        jsi.compress = False
    else:
        jsi.compress = True
        
    if args.dry:
        jsi.dry_run = 1

    if args.aria2_log:
        jsi.aria2_log = True

    if args.aria2_options:
        jsi.aria2_options = args.aria2_options

    if args.output_dir:
        # Add trailing slash if missing
        if args.output_dir[-1:] != '/':
            args.output_dir += '/'
        jsi.output_dir = args.output_dir

    # parameters which can be edited for a torrent

    if args.ratio:
        jsi.ratio = args.ratio
        jsi.edit_append('ratio')

    if args.add_tracker:
        jsi.add_tracker_url = args.add_tracker
        jsi.edit_append('add_tracker')

    if args.delete_tracker:
        jsi.delete_tracker_url = args.delete_tracker
        jsi.edit_append('delete_tracker')

    if args.name or args.name == "":
        jsi.name = args.name
        jsi.edit_append('name')

    if args.label or args.label == "":
        jsi.label = args.label
        jsi.edit_append('label')

    if args.version:
        print "Version", JSI_VERSION
        sys.exit()

    # Perform main actions

    # Check for problems first, like conflicting commands
    if (args.list_incomplete or args.list_complete) and args.list:
        sys.stderr.write("Can not use both --list-incomplete or --list-complete together with --list. Use them on its own.\n")
        sys.exit()

    if args.list_incomplete and args.list_complete:
        sys.stderr.write("Can not use both --list-incomplete and --list-complete in the one command\n")
        sys.exit()

    # No problems

    if args.magnet:
        jsi.add_magnet(args.magnet)
        
    elif args.torrent_file:
        jsi.add_torrent_file(args.torrent_file)

    elif args.infohash:
        jsi.add_infohash(args.infohash)

    elif args.list:
        jsi.list()

    elif args.list_incomplete:
        # List only incomplete torrents
        jsi.list_incomplete_only = True
        jsi.list()

    elif args.list_complete:
        # List only 100% completed torrents
        jsi.list_complete_only = True
        jsi.list()

    elif args.list_stopped:
        # List only 100% completed torrents
        jsi.list_stopped_only = True
        jsi.list()

    elif args.list_transfer:
        # List only torrents with data transfers in progress
        jsi.list_transfer_only = True
        jsi.list()

    elif args.list_links:
        # List only torrents with data transfers in progress
        print jsi.list_links()

    elif args.info:
        jsi.info(args.info)

    elif args.edit:
        jsi.edit(args.edit)
 
    #elif args.infomap:
    #    jsi.info_map()

    elif args.pieces:
        # show pretty list of pieces for this torrent
        print "Pieces for " + Style.BRIGHT + "{}".format(args.pieces) + Style.RESET_ALL
        jsi.pieces(args.pieces)
        rows = minidom.parseString(jsi.xml_response).getElementsByTagName("row")
        if len(rows):
            print "NUMBER HASH SIZE LINK"
        else:
            sys.stderr.write("No pieces available for this torrent.\n")

        for row in rows:
            # hash, number, size, url
            print "{} {} {} {}".format(
                Fore.WHITE + row.getElementsByTagName('number')[0].firstChild.nodeValue,
                Fore.CYAN + row.getElementsByTagName('hash')[0].firstChild.nodeValue,
                Fore.GREEN + row.getElementsByTagName('size')[0].firstChild.nodeValue,
                Fore.WHITE + urllib.unquote(row.getElementsByTagName('url')[0].firstChild.nodeValue) + "&api_key=" + jsi.api_key + Fore.RESET
            )

    elif args.pieces_aria2:
        jsi.pieces_aria2(args.pieces_aria2)

    elif args.pieces_sha1sum:
        jsi.pieces_sha1sum(args.pieces_sha1sum)

    elif args.start:
        jsi.start(args.start)

    elif args.stop:
        jsi.stop(args.stop)

    elif args.reset:
        jsi.reset(args.reset)

    elif args.delete:
        jsi.delete(args.delete)

    elif args.delete_stopped:
        jsi.delete_stopped()

    elif args.bitfield:
        param = jsi.expand(args.bitfield)

        for infohash in param:
            jsi.bitfield(infohash)

    elif args.trackers:
        param = jsi.expand(args.trackers)

        for infohash in param:
            print "Trackers for " + Style.BRIGHT + "{}".format(infohash) + Style.RESET_ALL
            jsi.trackers(infohash)
            rows = minidom.parseString(jsi.xml_response).getElementsByTagName("row")
            for row in rows:
                print "  " + urllib.unquote(row.getElementsByTagName('url')[0].firstChild.nodeValue) +\
                    " S:" + Style.BRIGHT + Fore.GREEN + row.getElementsByTagName('seeders')[0].firstChild.nodeValue + Style.RESET_ALL +\
                    " P:" + Style.BRIGHT + Fore.CYAN + row.getElementsByTagName('peers')[0].firstChild.nodeValue + Style.RESET_ALL +\
                    " L:" + Style.BRIGHT + Fore.WHITE + row.getElementsByTagName('leechers')[0].firstChild.nodeValue + Style.RESET_ALL

    elif args.peers:
        param = jsi.expand(args.peers)

        for infohash in param:
            data = jsi.peers(infohash)
            peers = minidom.parseString(data).getElementsByTagName("row")
            #if len(param):
            #    print "---"
            if len(peers):
                print "Connected Peers for " + Style.BRIGHT + "{}".format(infohash) + Style.RESET_ALL + ": {}".format(len(peers))
                for peer in peers:
                    peer_direction = peer.getElementsByTagName('direction')[0].firstChild.nodeValue
                    peer_ip = peer.getElementsByTagName('ip_address')[0].firstChild.nodeValue
                    peer_port = peer.getElementsByTagName('port')[0].firstChild.nodeValue
                    peer_id = jsi.urldecode_to_ascii(peer.getElementsByTagName('peer_id')[0].firstChild.nodeValue)
                    peer_percentage = peer.getElementsByTagName('percentage_as_decimal')[0].firstChild.nodeValue
                    if float(peer_percentage) == 100.0:
                        print "{:>3} {:>5} ".format(peer_direction, peer_id) +\
                              Fore.GREEN + "{:>6}".format(float(peer_percentage)) + Fore.RESET + "% " +\
                              Style.BRIGHT + Fore.BLUE + "{}".format(peer_ip) + Fore.RESET + Style.RESET_ALL + ":{}".format(peer_port) + Fore.RESET
                    else:
                        print "{:>3} {:>5} ".format(peer_direction, peer_id) +\
                              Fore.RED + "{:>6}".format(float(peer_percentage)) + Fore.RESET + "% " +\
                              Style.BRIGHT + Fore.BLUE + "{}".format(peer_ip) + Fore.RESET + Style.RESET_ALL + ":{}".format(peer_port) + Fore.RESET

            else:
                print "Connected Peers for " + Style.BRIGHT + "{}".format(infohash) + Style.RESET_ALL + ": {}".format(len(peers))
                continue

    elif args.files:
        # display coloured file name and size info
        jsi.files_pretty(args.files)

    elif args.files_csv:
        # write csv output, representing files information
        jsi.files_csv(args.files_csv)

    elif args.download_links:
        urls = jsi.download_links(args.download_links)
        for line in urls:
            print line

    elif args.download_links_renew:
        jsi.download_links_renew(args.download_links_renew)

    elif args.aria2:
        if args.aria2_options:
            jsi.aria2_options = args.aria2_options
        elif os.getenv('JSI_ARIA2_OPTIONS'):
            jsi.aria2_options = os.getenv('JSI_ARIA2_OPTIONS')

        jsi.aria2_script(args.aria2)

    elif args.list_tags:
        jsi.api("/tags/list.csp")

    elif args.list_variables:
        jsi.api("/variables/list.csp")

    else:
        parser.print_help()
        
    if args.pause:
        raw_input("Press Enter to continue...")
        
    sys.exit()
 