:: Run this within a Window Virtual Machines to configure a Rescuezilla Integration Test TCP server
::
:: Easiest way to get this script into an initialized Rescuezilla Integration Test Suite VM is to add a
:: second VirtualBox network interface (either NAT or Bridged adapter", then run `python -m http.server`
:: in the current folder. Then use Microsoft Edge to navigate to <ip>:8000 and download the batch file.
::
:: Then open a administrative CMD and run it: C:\Users\username\Downloads\install_windows_query_tcp_server.bat'

bcdedit> C:\cached_bcdedit.txt

:: Create batch file that opens a TCP socket on port 9999, and output system information using 'bcdedit'
echo "C:\Program Files (x86)\Nmap\ncat.exe" -l -p 9999 -c "type C:\cached_bcdedit.txt"> C:\rescuezilla.integration.test.server.bat

:: Download nmap as it contains the Windows netcat software 'ncat'
curl "https://nmap.org/dist/nmap-7.92-setup.exe" -o "C:\nmap-7.92-setup.exe"

:: Download Non-Sucking Service Manager (because Windows service manager can't run Batch files)
curl "https://nssm.cc/release/nssm-2.24.zip" -o C:\nssm-2.24.zip

echo "Runing the nmap installer. Make sure to install Nmap core files and Ncat"
:: There does not appear to be a /s (silent) install option, so install it manually.
C:\nmap-7.92-setup.exe

echo "Unzip using PowerShell 5 (only on Windows 10 or newer)"
powershell -command "Expand-Archive -LiteralPath 'C:\nssm-2.24.zip' -DestinationPath 'C:\.' -Force"

:: Add firewall exceptions
netsh advfirewall firewall add rule name="Rescuezilla Test Server" dir=in action=allow protocol=TCP localport=9999
netsh advfirewall firewall add rule name="Rescuezilla Test Server" dir=out action=allow protocol=TCP localport=9999

:: Create Rescuezilla Test Server Windows service
C:\nssm-2.24\win64\nssm.exe install rescuezilla.test.server.service "C:\rescuezilla.integration.test.server.bat"
C:\nssm-2.24\win64\nssm.exe set rescuezilla.test.server.service Description Rescuezilla Integration Test Server Service 
:: Configure auto start
C:\nssm-2.24\win64\nssm.exe set rescuezilla.test.server.service Start SERVICE_AUTO_START
:: Delay restart if application exits before 500ms (default 1500ms)
C:\nssm-2.24\win64\nssm.exe set rescuezilla.test.server.service AppThrottle 500
C:\nssm-2.24\win64\nssm.exe set rescuezilla.test.server.service AppExit Default Restart
C:\nssm-2.24\win64\nssm.exe set rescuezilla.test.server.service AppRestartDelay 0
:: Start the service
C:\nssm-2.24\win64\nssm.exe restart rescuezilla.test.server.service
