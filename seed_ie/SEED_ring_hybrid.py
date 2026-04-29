#!/usr/bin/env python3
# encoding: utf-8

from seedemu.layers import Base, Routing, Ospf
from seedemu.compiler import Docker, Platform
from seedemu.core import Emulator


def run():
    emu = Emulator()
    base = Base()
    routing = Routing()
    ospf = Ospf()

    ring = base.createAutonomousSystem(100)

    # Internal 6-ring networks
    ring.createNetwork('net12', '10.0.12.0/24')
    ring.createNetwork('net23', '10.0.23.0/24')
    ring.createNetwork('net34', '10.0.34.0/24')
    ring.createNetwork('net45', '10.0.45.0/24')
    ring.createNetwork('net56', '10.0.56.0/24')
    ring.createNetwork('net61', '10.0.61.0/24')

    # External gateway network for hybrid testing
    ring.createNetwork('netext', '10.0.200.0/24')


    ring.createNetwork('sr1test', '10.200.1.0/24')
    ring.createNetwork('sr2test', '10.200.2.0/24')
    ring.createNetwork('sr3test', '10.200.3.0/24')
    ring.createNetwork('sr4test', '10.200.4.0/24')
    ring.createNetwork('sr5test', '10.200.5.0/24')
    ring.createNetwork('sr6test', '10.200.6.0/24')



    sr1 = ring.createRouter('sr1')
    sr2 = ring.createRouter('sr2')
    sr3 = ring.createRouter('sr3')
    sr4 = ring.createRouter('sr4')
    sr5 = ring.createRouter('sr5')
    sr6 = ring.createRouter('sr6')

    for r in [sr1, sr2, sr3, sr4, sr5, sr6]:
        r.addSoftware('iperf3')
        r.addSoftware('iputils-ping')
        r.addSoftware('traceroute')
        r.addSoftware('net-tools')

    # 6-ring OSPF topology
    sr1.joinNetwork('net12', '10.0.12.254').joinNetwork('net61', '10.0.61.254')
    sr2.joinNetwork('net12', '10.0.12.253').joinNetwork('net23', '10.0.23.254')
    sr3.joinNetwork('net23', '10.0.23.253').joinNetwork('net34', '10.0.34.254')
    sr4.joinNetwork('net34', '10.0.34.253').joinNetwork('net45', '10.0.45.254')
    sr5.joinNetwork('net45', '10.0.45.253').joinNetwork('net56', '10.0.56.254')
    sr6.joinNetwork('net56', '10.0.56.253').joinNetwork('net61', '10.0.61.253')

    # r1 becomes the SEED-side gateway router
    sr1.joinNetwork('netext', '10.0.200.254')

    # Real-world router: sends traffic outside the SEED emulator.
    # This follows the SEED hybrid example pattern using createRealWorldRouter.
    rw = ring.createRealWorldRouter(
        'rw-mininet-gateway',
        prefixes=[
            '192.168.5.0/24'
        ]
    )
    rw.joinNetwork('netext','10.0.200.253')

    # Useful tools on real-world gateway container
    rw.addSoftware('iputils-ping')
    rw.addSoftware('traceroute')
    rw.addSoftware('net-tools')
    rw.addSoftware('iptables')


    sr1.joinNetwork('sr1test', '10.200.1.10')
    sr2.joinNetwork('sr2test', '10.200.2.10')
    sr3.joinNetwork('sr3test', '10.200.3.10')
    sr4.joinNetwork('sr4test', '10.200.4.10')
    sr5.joinNetwork('sr5test', '10.200.5.10')
    sr6.joinNetwork('sr6test', '10.200.6.10')

    emu.addLayer(base)
    emu.addLayer(routing)
    emu.addLayer(ospf)

    emu.render()

    docker = Docker(platform=Platform.AMD64)
    emu.compile(docker, './output_hybrid', override=True)


if __name__ == "__main__":
    run()
