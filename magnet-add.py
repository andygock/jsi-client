#!/usr/bin/env python
"""
Helper script to add torrent by magnet link. Designed to be compiled and set as default application in web browser.
"""

import jsi
import argparse
import sys

parser = argparse.ArgumentParser(prog='magnet-add.py', description='Helper script to add torrent by magnet link. Designed to be compiled and set as default application in web browser.')
parser.add_argument("magnets", type=str, nargs='+')

args = parser.parse_args()

jsi = jsi.JustSeedIt()
jsi.verbose = True

for magnet in args.magnets:
    sys.stderr.write("Adding \"{}\"\n".format(magnet))
    jsi.add_magnet(magnet)

try:
    input("Press ENTER to continue...")
except SyntaxError:
    pass
