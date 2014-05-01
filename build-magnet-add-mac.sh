#!/bin/sh
rm -rf setup.py setup-macosx.py
py2applet --make-setup magnet-add.py
mv setup.py setup-macosx.py
rm -rf build/ dist/
python setup-macosx.py py2app
rm -rf /Applications/magnet-add.app
cp -R dist/magnet-add.app /Applications
