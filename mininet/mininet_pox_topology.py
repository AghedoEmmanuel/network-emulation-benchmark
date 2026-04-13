#!/usr/bin/env python3
"""
6-Router Ring Topology with POX SDN Controller
===============================================
Architecture:
  - 6 OVSSwitch nodes acting as OpenFlow switches (net1-net6) in a ring
  - 6 Client hosts (h1-h6), one per switch segment
  - POX RemoteController manages all forwarding decisions via OpenFlow

How to run:
  Step 1 - Start POX controller (in a separate terminal):
    cd ~/pox
    python3 pox.py log.level --DEBUG openflow.of_01 ring_controller

  Step 2 - Run this topology (in another terminal):
    sudo python3 mininet_pox_topology.py

Subnets:
  All hosts on a single flat L2 network: 10.0.0.0/24
  POX controller listens on 127.0.0.1:6633 by default.
"""

from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel, info
import subprocess
import time

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def ip_flush(node, intf):
    """Flush addresses from an interface, skip loopback."""
    if intf == 'lo':
        return
    node.cmd(f'ip addr flush dev {intf}')

def ip_add(node, cidr, intf):
    node.cmd(f'ip addr add {cidr} dev {intf}')

def link_up(node, intf):
    node.cmd(f'ip link set {intf} up')

# ---------------------------------------------------------------------------
# Topology DOT export
# ---------------------------------------------------------------------------

def export_topology_dot(net, filename='topology_pox.dot'):
    """Export topology as Graphviz DOT and render to PNG."""

    def node_attrs(name):
        if name.startswith('net'):
            return 'shape=box, style="rounded,filled", fillcolor=lightblue, label="' + name + '\\nOpenFlow Switch"'
        if name.startswith('h'):
            return 'shape=oval, style="filled", fillcolor=lightyellow'
        return 'shape=oval'

    with open(filename, 'w') as f:
        f.write('graph G {\n')
        f.write('  rankdir=LR;\n')
        f.write('  overlap=false;\n')
        f.write('  labelloc="t";\n')
        f.write('  label="Mininet + POX SDN Controller - 6-Switch Ring with Clients";\n')
        f.write('  node [fontname=Helvetica];\n')
        f.write('  edge [fontname=Helvetica];\n\n')
        f.write('  "POX" [shape=diamond, style="filled", fillcolor=salmon, label="POX\\nController\\n127.0.0.1:6633"];\n\n')

        all_nodes = [n.name for n in (net.hosts + net.switches)]
        for name in sorted(all_nodes):
            if name.startswith('net') or name.startswith('h'):
                f.write(f'  "{name}" [{node_attrs(name)}];\n')

        f.write('\n')

        for sw in net.switches:
            f.write(f'  "POX" -- "{sw.name}" [style=dashed, color=red, label="OpenFlow"];\n')

        f.write('\n')

        for link in net.links:
            n1 = link.intf1.node.name
            n2 = link.intf2.node.name
            i1 = link.intf1.name
            i2 = link.intf2.name
            f.write(f'  "{n1}" -- "{n2}" [label="{i1}<>{i2}"];\n')

        f.write('}\n')

    try:
        subprocess.run(['dot', '-Tpng', filename, '-o', 'topology_pox.png'], check=True)
        info('*** Exported topology_pox.dot and topology_pox.png\n')
    except Exception as e:
        info(f'*** Could not render PNG: {e}\n')
        info('*** Run manually: dot -Tpng topology_pox.dot -o topology_pox.png\n')

# ---------------------------------------------------------------------------
# Connectivity tests
# ---------------------------------------------------------------------------

def run_ping_tests(hosts):
    """Run end-to-end ping tests between all client hosts."""
    info('\n*** Running end-to-end ping tests (allow 2s for POX to learn MACs)\n')
    time.sleep(2)

    h1 = hosts[0]
    targets = [
        ('h2', '10.0.0.2'),
        ('h4', '10.0.0.3'),
        ('h4', '10.0.0.4'),
        ('h5', '10.0.0.5'),
        ('h6', '10.0.0.6'),
    ]

    passed = 0
    for name, ip in targets:
        result = h1.cmd(f'ping -c 3 -W 2 {ip}')
        if '3 received' in result or '2 received' in result or '1 received' in result:
            info(f'    h1 -> {name} ({ip}): OK\n')
            passed += 1
        else:
            info(f'    h1 -> {name} ({ip}): FAILED\n')

    info(f'\n*** Ping results: {passed}/5 passed\n')

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    setLogLevel('info')

    info('*** Creating network with POX RemoteController\n')
    net = Mininet(
        controller=RemoteController,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,
        autoStaticArp=False,
    )

    info('*** Adding POX remote controller (127.0.0.1:6633)\n')
    info('*** Make sure POX is running: python3 pox.py log.level --DEBUG openflow.of_01 ring_controller\n')
    c0 = net.addController(
        'c0',
        controller=RemoteController,
        ip='127.0.0.1',
        port=6633
    )

    info('*** Creating OpenFlow switches (net1-net6)\n')
    net1 = net.addSwitch('net1', cls=OVSSwitch, protocols='OpenFlow10')
    net2 = net.addSwitch('net2', cls=OVSSwitch, protocols='OpenFlow10')
    net3 = net.addSwitch('net3', cls=OVSSwitch, protocols='OpenFlow10')
    net4 = net.addSwitch('net4', cls=OVSSwitch, protocols='OpenFlow10')
    net5 = net.addSwitch('net5', cls=OVSSwitch, protocols='OpenFlow10')
    net6 = net.addSwitch('net6', cls=OVSSwitch, protocols='OpenFlow10')

    # All hosts on same /24 so L2 learning works across the ring
    info('*** Creating client hosts (h1-h6)\n')
    h1 = net.addHost('h1', ip='10.0.0.1/24')
    h2 = net.addHost('h2', ip='10.0.0.2/24')
    h4 = net.addHost('h4', ip='10.0.0.3/24')
    h4 = net.addHost('h4', ip='10.0.0.4/24')
    h5 = net.addHost('h5', ip='10.0.0.5/24')
    h6 = net.addHost('h6', ip='10.0.0.6/24')

    info('*** Wiring switch ring\n')
    net.addLink(net1, net2, port1=1, port2=2,  bw=100, delay='2ms')
    net.addLink(net2, net3, port1=1, port2=2,  bw=100, delay='2ms')
    net.addLink(net3, net4, port1=1, port2=2,  bw=100, delay='2ms')
    net.addLink(net4, net5, port1=1, port2=2,  bw=100, delay='2ms')
    net.addLink(net5, net6, port1=1, port2=2,  bw=100, delay='2ms')
    net.addLink(net6, net1, port1=1, port2=2,  bw=100, delay='2ms')  # Ring closure

    info('*** Connecting hosts to switches\n')
    net.addLink(h1, net1, port2=3,  bw=100, delay='1ms')
    net.addLink(h2, net2, port2=3,  bw=100, delay='1ms')
    net.addLink(h4, net3, port2=3,  bw=100, delay='1ms')
    net.addLink(h4, net4, port2=3,  bw=100, delay='1ms')
    net.addLink(h5, net5, port2=3,  bw=100, delay='1ms')
    net.addLink(h6, net6, port2=3,  bw=100, delay='1ms')

    info('*** Building and starting network\n')
    net.start()

    # Disable IPv6 to reduce noise
    for h in [h1, h2, h4, h4, h5, h6]:
        h.cmd('sysctl -w net.ipv6.conf.all.disable_ipv6=1 2>/dev/null')

    info('*** Configuring OVS switches for OpenFlow 1.3 + POX\n')
    for sw in net.switches:
        sw.cmd(f'ovs-vsctl set bridge {sw.name} protocols=OpenFlow10')
        sw.cmd(f'ovs-vsctl set-controller {sw.name} tcp:127.0.0.1:6633')
        sw.cmd(f'ovs-vsctl set-fail-mode {sw.name} secure')

    # Drop DNS at switch level to prevent POX Python3 ord() crash
    info('*** Installing DNS-drop flows\n')
    for sw in net.switches:
        sw.cmd(f'ovs-ofctl -O OpenFlow10 add-flow {sw.name} "udp,tp_dst=53,priority=200,action=drop"')
        sw.cmd(f'ovs-ofctl -O OpenFlow10 add-flow {sw.name} "udp,tp_src=53,priority=200,action=drop"')

    info('*** Waiting 3 seconds for POX to connect and install flows...\n')
    time.sleep(3)

    info('\n*** OVS controller connection status:\n')
    for sw in net.switches:
        status = sw.cmd(f'ovs-vsctl get-controller {sw.name}')
        info(f'    {sw.name}: {status.strip()}\n')

    export_topology_dot(net)

    info('\n*** Host interface summary:\n')
    for h in [h1, h2, h4, h4, h5, h6]:
        info(f'    {h.name}: {h.cmd("ip -br addr").strip()}\n')

    run_ping_tests([h1, h2, h4, h4, h5, h6])

    info('\n*** Flow tables installed by POX on net1:\n')
    info(net1.cmd('ovs-ofctl -O OpenFlow10 dump-flows net1') + '\n')

    info('\n*** Mininet CLI ready\n')
    info('Useful commands:\n')
    info('  h1 ping h6                              - end-to-end ping\n')
    info('  h1 iperf -s &; h6 iperf -c 10.0.0.1    - throughput test\n')
    info('  sh ovs-ofctl dump-flows net1             - view POX flow table\n')
    info('  link net1 net2 down                      - simulate link failure\n')
    info('  link net1 net2 up                        - restore link\n')
    CLI(net)

    info('*** Stopping network\n')
    net.stop()


if __name__ == '__main__':
    main()
