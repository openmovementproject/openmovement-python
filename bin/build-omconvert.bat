@echo off
cd /d "%~dp0"
powershell -Command "& {Invoke-WebRequest https://github.com/digitalinteraction/omconvert/archive/master.zip -o omconvert.build.zip ; Expand-Archive omconvert.build.zip ; del omconvert.build.zip ; omconvert.build/omconvert-master/src/omconvert/build.cmd ; copy omconvert.build/omconvert-master/src/omconvert/omconvert.exe . }"
