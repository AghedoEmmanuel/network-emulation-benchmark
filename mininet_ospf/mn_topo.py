#!/usr/bin/python3
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import Node
from mininet.log import setLogLevel, info
from mininet.cli import CLI


class LinuxRouter(Node):
    # def config(self, **params):
    #     super(LinuxRouter, self).config(**params)
    def config(self, **params):
        super(LinuxRouter, self).config(**params)
        self.cmd('sysctl -w net.ipv4.ip_forward=1 >/dev/null')
        self.cmd('sysctl -w net.ipv6.conf.all.disable_ipv6=1 >/dev/null 2>&1')

    # def terminate(self):
        # super(LinuxRouter, self).terminate()
        def terminate(self):
            self.cmd('sysctl -w net.ipv4.ip_forward=0 >/dev/null')
            super(LinuxRouter, self).terminate()


class NetworkTopo(Topo):
    def build(self, **_opts):
        # Add 2 routers with two different subnets
        # r1 = self.addHost('r1', cls=LinuxRouter, ip='10.1.0.1/24')
        # r2 = self.addHost('r2', cls=LinuxRouter, ip='10.3.0.1/24')
        # r3 = self.addHost('r3', cls=LinuxRouter, ip='10.5.0.1/24')
        # r4 = self.addHost('r4', cls=LinuxRouter, ip='10.7.0.1/24')
        # 6-router OSPF ring aligned to SEED_Ring.py
        r1 = self.addHost('r1', cls=LinuxRouter, ip=None)
        r2 = self.addHost('r2', cls=LinuxRouter, ip=None)
        r3 = self.addHost('r3', cls=LinuxRouter, ip=None)
        r4 = self.addHost('r4', cls=LinuxRouter, ip=None)
        r5 = self.addHost('r5', cls=LinuxRouter, ip=None)
        r6 = self.addHost('r6', cls=LinuxRouter, ip=None)

        # Add 2 switches, two for each subnet
        # s11 = self.addSwitch('s11')
        # s12 = self.addSwitch('s12')
        # s21 = self.addSwitch('s21')
        # s22 = self.addSwitch('s22')
        # s31 = self.addSwitch('s31')
        # s32 = self.addSwitch('s32')
        # s41 = self.addSwitch('s41')
        # s42 = self.addSwitch('s42')

        # Connect switches to routers
        # self.addLink(
        #     r1,r2,
        #     intfName2='r1-eth1',
        #     params2={'ip': '10.1.0.1/24'}
        #     )

        # self.addLink(
        #     s12,
        #              r1,
        #              intfName2='r1-eth2',
        #              params2={'ip': '10.2.0.1/24'})

        # self.addLink(s21,
        #              r2,
        #              intfName2='r2-eth1',
        #              params2={'ip': '10.3.0.1/24'})

        # self.addLink(s22,
        #              r2,
        #              intfName2='r2-eth2',
        #              params2={'ip': '10.4.0.1/24'})

        # self.addLink(s31,
        #              r3,
        #              intfName2='r3-eth1',
        #              params2={'ip': '10.5.0.1/24'})

        # self.addLink(s32,
        #              r3,
        #              intfName2='r3-eth2',
        #              params2={'ip': '10.6.0.1/24'})

        # self.addLink(s41,
        #              r4,
        #              intfName2='r4-eth1',
        #              params2={'ip': '10.7.0.1/24'})

        # self.addLink(s42,
        #              r4,
        #              intfName2='r4-eth2',
        #              params2={'ip': '10.8.0.1/24'})


        # Add router-router link in a new subnet
        # self.addLink(r1,
        #              r2,
        #              intfName1='r1-eth3',
        #              intfName2='r2-eth3',
        #              params1={'ip': '10.100.0.1/24'},
        #              params2={'ip': '10.100.0.2/24'})
        # self.addLink(r2,
        #              r3,
        #              intfName1='r2-eth4',
        #              intfName2='r3-eth4',
        #              params1={'ip': '10.101.0.1/24'},
        #              params2={'ip': '10.101.0.2/24'})
        # self.addLink(r3,
        #              r4,
        #              intfName1='r3-eth3',
        #              intfName2='r4-eth3',
        #              params1={'ip': '10.102.0.1/24'},
        #              params2={'ip': '10.102.0.2/24'})
        # self.addLink(r4,
        #              r1,
        #              intfName1='r4-eth4',
        #              intfName2='r1-eth4',
        #              params1={'ip': '10.103.0.1/24'},
        #              params2={'ip': '10.103.0.2/24'})
        
        self.addLink(
            r1, r2,
            intfName1='r1-eth1',
            intfName2='r2-eth1',
            params1={'ip': '10.0.12.1/24'},
            params2={'ip': '10.0.12.2/24'}
        )
        self.addLink(
            r2, r3,
            intfName1='r2-eth2',
            intfName2='r3-eth1',
            params1={'ip': '10.0.23.1/24'},
            params2={'ip': '10.0.23.2/24'}
        )
        self.addLink(
            r3, r4,
            intfName1='r3-eth2',
            intfName2='r4-eth1',
            params1={'ip': '10.0.34.1/24'},
            params2={'ip': '10.0.34.2/24'}
        )
        self.addLink(
            r4, r5,
            intfName1='r4-eth2',
            intfName2='r5-eth1',
            params1={'ip': '10.0.45.1/24'},
            params2={'ip': '10.0.45.2/24'}
        )
        self.addLink(
            r5, r6,
            intfName1='r5-eth2',
            intfName2='r6-eth1',
            params1={'ip': '10.0.56.1/24'},
            params2={'ip': '10.0.56.2/24'}
        )
        self.addLink(
            r6, r1,
            intfName1='r6-eth2',
            intfName2='r1-eth2',
            params1={'ip': '10.0.61.1/24'},
            params2={'ip': '10.0.61.2/24'}
        )

        # Adding hosts with a default route
        # d1 = self.addHost(name='d1',
        #                   ip='10.1.0.251/24',
        #                   defaultRoute='via 10.1.0.1')
        # d2 = self.addHost(name='d2',
        #                   ip='10.2.0.252/24',
        #                   defaultRoute='via 10.2.0.1')
        # d3 = self.addHost(name='d3',
        #                   ip='10.3.0.251/24',
        #                   defaultRoute='via 10.3.0.1')
        # d4 = self.addHost(name='d4',
        #                   ip='10.4.0.252/24',
        #                   defaultRoute='via 10.4.0.1')
        # d5 = self.addHost(name='d5',
        #                   ip='10.5.0.251/24',
        #                   defaultRoute='via 10.5.0.1')
        # d6 = self.addHost(name='d6',
        #                   ip='10.6.0.252/24',
        #                   defaultRoute='via 10.6.0.1')
        # d7 = self.addHost(name='d7',
        #                   ip='10.7.0.251/24',
        #                   defaultRoute='via 10.7.0.1')
        # d8 = self.addHost(name='d8',
        #                   ip='10.8.0.252/24',
        #                   defaultRoute='via 10.8.0.1')
 
 
        # Add host-switch links
        # self.addLink(d1, s11)
        # self.addLink(d2, s12)
        # self.addLink(d3, s21)
        # self.addLink(d4, s22)
        # self.addLink(d5, s31)
        # self.addLink(d6, s32)
        # self.addLink(d7, s41)
        # self.addLink(d8, s42)

def run():
    topo = NetworkTopo()
    net = Mininet(topo=topo)
    net.start()

    # info(net['r1'].cmd("/usr/lib/frr/frrinit.sh start 'r1'"))
    # info(net['r2'].cmd("/usr/lib/frr/frrinit.sh start 'r2'"))
    # info(net['r3'].cmd("/usr/lib/frr/frrinit.sh start 'r3'"))
    # info(net['r4'].cmd("/usr/lib/frr/frrinit.sh start 'r4'"))

    # net.start()
    # CLI(net)

    # info(net['r1'].cmd("/usr/lib/frr/frrinit.sh stop 'r1'"))
    # info(net['r2'].cmd("/usr/lib/frr/frrinit.sh stop 'r2'"))
    # info(net['r3'].cmd("/usr/lib/frr/frrinit.sh stop 'r3'"))
    # info(net['r4'].cmd("/usr/lib/frr/frrinit.sh stop 'r4'"))
    
    # Start FRR per router after Mininet starts
    for node in ('r1', 'r2', 'r3', 'r4', 'r5', 'r6'):
        info(net[node].cmd(f"/usr/lib/frr/frrinit.sh start '{node}'"))

    info("\nUseful checks:\n")
    info("  r1 vtysh -N r1 -c \"show ip ospf neighbor\"\n")
    info("  r1 vtysh -N r1 -c \"show ip route ospf\"\n")
    info("  r1 ping 10.0.56.2\n")
    info("  r1 traceroute 10.0.56.2\n\n")

    CLI(net)

    for node in ('r1', 'r2', 'r3', 'r4', 'r5', 'r6'):
        info(net[node].cmd(f"/usr/lib/frr/frrinit.sh stop '{node}'"))

    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    run()


