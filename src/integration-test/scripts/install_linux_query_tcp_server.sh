#!/bin/bash
#
# Install a simple TCP server to enable Rescuezilla's Integration Test Suite to
# check if a restored machine is able to boot after being restored.
#
# Copy over to any modern Linux that has the pre-requisites:
#     bash, nc, lsb_release, systemd
#
# Note: This script can usually be copied WITHOUT installing an SSH server or
# using a VirtualBox shared folder. Assuming host can ping guest VM (eg, 192.168.60.2):
#     On the guest VM, open netcat TCP listening port (may need to add a firewall exception)
#         nc -l -p 2000 -q 1 > /tmp/install.sh
#
#     On the host environment, send over file:
#         cat install_linux_query_tcp_server.sh | nc -q 1 192.168.60.2 2000
# 
# To install, run the following:
#     # On guest VM:
#     sudo bash ./tmp/install.sh
#
#     # On host environment, connect and confirm response:
#     nc 192.168.60.2 9999
#
# Once installed, create backups using Rescuezilla, Clonezilla etc, and integrate the
# details of the backup image into Rescuezilla's Integration Test Suite Python script

set -x

# Some machines don't have lsb_release installed. In which case, get the data from /etc/os-release
if command -v lsb_release &> /dev/null
then
    COMMAND="lsb_release --short --description"
else
    COMMAND=". /etc/os-release; echo \$NAME \$VERSION"
fi

# Some versions of netcat don't seem to support the useful "-q" argument ("quit after EOF on stdin and delay of secs")
nc -h 2>&1 | egrep -- ".*-q .*"
RC=$?
if [ $RC -eq 0 ]; then
    NC_ARGS="-q 0"
fi

cat << EOF > /rescuezilla.integration.test.server.sh
#!/bin/bash
set -x
# Open a TCP socket on port 9999, and exit on stdin EOF
$COMMAND | nc -l -p 9999 $NC_ARGS
EOF


cat << EOF > /etc/systemd/system/rescuezilla.test.server.service
[Unit]
Description=Rescuezilla Integration Test Server service
After=network.target
StartLimitIntervalSec=1

[Service]
Type=simple
ExecStart="/rescuezilla.integration.test.server.sh"
RestartSec=1
Restart=always

[Install]
WantedBy=multi-user.target
EOF
chmod 755  /rescuezilla.integration.test.server.sh

if command -v firewall-cmd &> /dev/null
then
    echo "Adding permanent CentOS firewall exception (firewalld) for the integration test server"
    sudo firewall-cmd --zone=public --permanent --add-port=9999/tcp
    sudo systemctl restart firewalld
fi

systemctl daemon-reload
systemctl enable rescuezilla.test.server.service
systemctl restart rescuezilla.test.server.service

