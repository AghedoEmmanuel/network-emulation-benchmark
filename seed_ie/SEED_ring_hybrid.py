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
    ring.createNetwork('netext', '10.0.99.0/24')

    r1 = ring.createRouter('r1')
    r2 = ring.createRouter('r2')
    r3 = ring.createRouter('r3')
    r4 = ring.createRouter('r4')
    r5 = ring.createRouter('r5')
    r6 = ring.createRouter('r6')

    for r in [r1, r2, r3, r4, r5, r6]:
        r.addSoftware('iperf3')
        r.addSoftware('iputils-ping')
        r.addSoftware('traceroute')
        r.addSoftware('net-tools')

    # 6-ring OSPF topology
    r1.joinNetwork('net12', '10.0.12.254').joinNetwork('net61', '10.0.61.254')
    r2.joinNetwork('net12', '10.0.12.253').joinNetwork('net23', '10.0.23.254')
    r3.joinNetwork('net23', '10.0.23.253').joinNetwork('net34', '10.0.34.254')
    r4.joinNetwork('net34', '10.0.34.253').joinNetwork('net45', '10.0.45.254')
    r5.joinNetwork('net45', '10.0.45.253').joinNetwork('net56', '10.0.56.254')
    r6.joinNetwork('net56', '10.0.56.253').joinNetwork('net61', '10.0.61.253')

    # r1 becomes the SEED-side gateway router
    r1.joinNetwork('netext', '10.0.99.254')

    # Real-world router: sends traffic outside the SEED emulator.
    # This follows the SEED hybrid example pattern using createRealWorldRouter.
    rw = ring.createRealWorldRouter(
        'rw-mininet-gateway',
        prefixes=[
            '192.168.5.0/24'
        ]
    )
    rw.joinNetwork('netext', '10.0.99.1')

    # Useful tools on real-world gateway container
    rw.addSoftware('iputils-ping')
    rw.addSoftware('traceroute')
    rw.addSoftware('net-tools')
    rw.addSoftware('iptables')

    emu.addLayer(base)
    emu.addLayer(routing)
    emu.addLayer(ospf)

    emu.render()

    docker = Docker(platform=Platform.AMD64)
    emu.compile(docker, './output_hybrid', override=True)


if __name__ == "__main__":
    run()