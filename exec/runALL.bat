:: SET TETRAD INPUT FILE
:: -----------------------------
SET DATFILE=RUN0
SET ISRESTART=N
SET RESFILE=

:: SET Working Dirs
:: -----------------------------
SET WKDIR="D:\Shared\PMBA\Scripts\GitRepos\tetrad-forecast\test"
SET SVRWKDIR="\\IBMHO-PC03E9Q5\Shared\PMBA\Scripts\GitRepos\tetrad-forecast\test\"
SET SVRWKDIRLOCAL="D:\Shared\PMBA\Scripts\GitRepos\tetrad-forecast\test\"
pushd %WKDIR%

:: CREATE INPUT FILE
:: -----------------------------
SET INFILE=inTETRAD.bat
ECHO %DATFILE%.DAT>  %INFILE%
ECHO.             >> %INFILE%
ECHO %ISRESTART%  >> %INFILE%
IF %ISRESTART%==Y (
ECHO %RESFILE%    >> %INFILE%
)

:: CREATE RUN FILE
:: -----------------------------
SET RUNFILE=runTETRAD.bat
ECHO PUSHD %SVRWKDIRLOCAL% > %RUNFILE%
ECHO TETRAD-G.exe ^< %INFILE% >> %RUNFILE%

:: COPY ALL FILES
:: -----------------------------
xcopy %WKDIR% %SVRWKDIR% /Y

:: CLEANUP
:: -----------------------------
DEL %INFILE%
DEL %RUNFILE%

:: RUN ON SERVER
:: -----------------------------
D:\Shared\Software\paexec.exe \\IBMHO-PC03E9Q5 "%SVRWKDIRLOCAL:"=%%RUNFILE%"

xcopy \\IBMHO-PC03E9Q5\Shared\PMBA\Scripts\GitRepos\tetrad-forecast\test\RUN0.OUT .\ /Y
xcopy \\IBMHO-PC03E9Q5\Shared\PMBA\Scripts\GitRepos\tetrad-forecast\test\RUN0_o.IS .\ /Y
