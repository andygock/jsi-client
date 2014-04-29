call build-jsi.cmd
call build-magnet-add.cmd
copy dist\magnet-add\magnet-add.exe dist\jsi\
del jsi.zip
cd dist\jsi
zip -9 ..\..\jsi.zip *
cd ..\..
pause
