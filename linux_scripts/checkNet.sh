#!/bin/bash

date
wget -q --tries=3 --timeout=5 --spider http://google.com
if [[ $? -eq 0 ]]; then
        echo "Online"
else
        echo "Offline"
        /usr/sbin/service openvpn stop
        echo "vpn stopped"
        /usr/sbin/service network-manager restart
        echo "network restarted"
        /usr/sbin/service openvpn start
        echo "Restarted OpenVPN"
fi

