"""
POX Ring Controller - Ring-Aware Proactive Path Installation
=============================================================
Place in: ~/pox/ext/ring_controller.py

Launch with:
  cd ~/pox
  python3 pox.py log.level --DEBUG openflow.of_01 ring_controller
"""

from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.util import dpid_to_str
from pox.lib.addresses import EthAddr, IPAddr
from pox.lib.packet import ethernet, arp

log = core.getLogger()

RING_ORDER = [1, 2, 3, 4, 5, 6]
NUM_SWITCHES = 6

PORT_RING_CW  = 1   # eth1: clockwise ring port
PORT_RING_CCW = 2   # eth2: anticlockwise ring port
PORT_HOST     = 3   # eth3: host-facing port

def host_mac(n):
    return EthAddr('00:00:00:00:00:0%d' % n)

def host_ip(n):
    return IPAddr('10.0.0.%d' % n)

def get_out_port(src_sw, dst_sw):
    """Return output port on src_sw to reach dst_sw via shortest ring path."""
    if dst_sw == src_sw:
        return PORT_HOST
    cw_dist  = (dst_sw - src_sw) % NUM_SWITCHES
    ccw_dist = (src_sw - dst_sw) % NUM_SWITCHES
    return PORT_RING_CW if cw_dist <= ccw_dist else PORT_RING_CCW


class RingSwitch(object):

    def __init__(self, connection, sw_num):
        self.connection = connection
        self.sw_num = sw_num
        connection.addListeners(self)
        log.info('Switch net%d connected (dpid=%s)', sw_num, dpid_to_str(connection.dpid))
        self._install_dns_drop()
        self._install_table_miss()
        self._install_ring_flows()

    def _install_dns_drop(self):
        for port in (53,):
            for field in ('tp_dst', 'tp_src'):
                msg = of.ofp_flow_mod()
                msg.priority = 200
                msg.match.dl_type = 0x0800
                msg.match.nw_proto = 17
                setattr(msg.match, field, port)
                self.connection.send(msg)  # no actions = drop

    def _install_table_miss(self):
        msg = of.ofp_flow_mod()
        msg.priority = 1
        msg.actions.append(of.ofp_action_output(port=of.OFPP_CONTROLLER))
        self.connection.send(msg)

    def _install_ring_flows(self):
        for dst in RING_ORDER:
            out_port = get_out_port(self.sw_num, dst)
            msg = of.ofp_flow_mod()
            msg.priority = 10
            msg.match.dl_dst = host_mac(dst)
            msg.actions.append(of.ofp_action_output(port=out_port))
            self.connection.send(msg)
            log.debug('net%d: dst=h%d -> port %d', self.sw_num, dst, out_port)

    def _handle_PacketIn(self, event):
        try:
            packet = event.parsed
            if not packet or not packet.parsed:
                return
            if packet.type == ethernet.ARP_TYPE:
                self._handle_arp(event, packet)
        except Exception as e:
            log.debug('PacketIn error: %s', str(e))

    def _handle_arp(self, event, packet):
        try:
            arp_pkt = packet.find('arp')
            if not arp_pkt or arp_pkt.opcode != arp.REQUEST:
                return

            target_ip = arp_pkt.protodst
            octets = str(target_ip).split('.')
            target_num = int(octets[-1])
            if target_num < 1 or target_num > NUM_SWITCHES:
                return

            target_mac = host_mac(target_num)
            log.info('net%d: ARP proxy %s -> %s = %s',
                     self.sw_num, arp_pkt.protosrc, target_ip, target_mac)

            arp_reply = arp()
            arp_reply.opcode   = arp.REPLY
            arp_reply.hwsrc    = target_mac
            arp_reply.hwdst    = arp_pkt.hwsrc
            arp_reply.protosrc = target_ip
            arp_reply.protodst = arp_pkt.protosrc

            eth_reply = ethernet()
            eth_reply.type    = ethernet.ARP_TYPE
            eth_reply.src     = target_mac
            eth_reply.dst     = arp_pkt.hwsrc
            eth_reply.payload = arp_reply

            msg = of.ofp_packet_out()
            msg.data = eth_reply.pack()
            msg.in_port = of.OFPP_NONE
            msg.actions.append(of.ofp_action_output(port=event.port))
            self.connection.send(msg)

        except Exception as e:
            log.debug('ARP proxy error: %s', str(e))


class RingController(object):

    def __init__(self):
        self.switches = {}
        core.openflow.addListeners(self)
        log.info('RingController ready - waiting for switches')

    def _handle_ConnectionUp(self, event):
        dpid = event.dpid
        sw_num = dpid & 0xFF
        if sw_num < 1 or sw_num > NUM_SWITCHES:
            sw_num = len(self.switches) + 1
        self.switches[dpid] = RingSwitch(event.connection, sw_num)
        log.info('Total switches connected: %d', len(self.switches))

    def _handle_ConnectionDown(self, event):
        if event.dpid in self.switches:
            del self.switches[event.dpid]
            log.warning('Switch disconnected: %s', dpid_to_str(event.dpid))


def launch():
    core.registerNew(RingController)
    log.info('Ring Controller launched successfully')
