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

    ring.createNetwork('net12', '10.0.12.0/24')
    ring.createNetwork('net23', '10.0.23.0/24')
    ring.createNetwork('net34', '10.0.34.0/24')
    ring.createNetwork('net45', '10.0.45.0/24')
    ring.createNetwork('net56', '10.0.56.0/24')
    ring.createNetwork('net61', '10.0.61.0/24')

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

    r1.joinNetwork('net12').joinNetwork('net61')
    r2.joinNetwork('net12').joinNetwork('net23')
    r3.joinNetwork('net23').joinNetwork('net34')
    r4.joinNetwork('net34').joinNetwork('net45')
    r5.joinNetwork('net45').joinNetwork('net56')
    r6.joinNetwork('net56').joinNetwork('net61')

    emu.addLayer(base)
    emu.addLayer(routing)
    emu.addLayer(ospf)

    emu.render()

    docker = Docker(platform=Platform.AMD64)
    emu.compile(docker, './output', override=True)


if __name__ == "__main__":
    run()
