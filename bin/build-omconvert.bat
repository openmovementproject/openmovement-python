@echo off
cd /d "%~dp0"
if not exist "..\..\..\src\omconvert\build.cmd" goto download_build
call "..\..\..\src\omconvert\build.cmd"
copy /y "..\..\..\src\omconvert\omconvert.exe" .
goto end

:download_build
powershell -Command "& {Invoke-WebRequest https://github.com/digitalinteraction/omconvert/archive/master.zip -o omconvert.build.zip ; Expand-Archive omconvert.build.zip ; del omconvert.build.zip ; omconvert.build/omconvert-master/src/omconvert/build.cmd ; copy omconvert.build/omconvert-master/src/omconvert/omconvert.exe . }"
goto end

:end
