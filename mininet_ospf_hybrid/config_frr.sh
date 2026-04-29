#!/bin/bash
set -e

for NODE in r1 r2 r3 r4 r5 r6
do
    sudo install -m 775 -o frr -g frr -d /var/log/frr/${NODE}
    sudo install -m 775 -o frr -g frrvty -d /etc/frr/${NODE}
    sudo install -m 775 -o frr -g frr -d -d /var/run/frr/${NODE}

    sudo install -m 640 -o frr -g frrvty ${NODE}/vtysh.conf \
	    /etc/frr/${NODE}/vtysh.conf
    sudo install -m 640 -o frr -g frr ${NODE}/frr.conf \
	    /etc/frr/${NODE}/frr.conf
    sudo install -m 640 -o frr -g frr ${NODE}/daemons  \
	    /etc/frr/${NODE}/daemons
    sudo sed -i 's/ospfd=no/ospfd=yes/' /etc/frr/${NODE}/daemons
    sudo sed -i 's/zebra=no/zebra=yes/' /etc/frr/${NODE}/daemons
done



