####################################################
# DVrouter.py
# Name:
# HUID:
#####################################################

from json import dumps, loads

from packet import Packet
from router import Router


class DVrouter(Router):
    """Distance vector routing protocol implementation.

    Add your own class fields and initialization code (e.g. to create forwarding table
    data structures). See the `Router` base class for docstrings of the methods to
    override.
    """

    def __init__(self, addr, heartbeat_time):
        Router.__init__(self, addr)  # Initialize base class - DO NOT REMOVE
        self.heartbeat_time = heartbeat_time
        self.last_time = 0
        self.neighbors = {}  # port -> (endpoint, outgoing cost)
        self.received = {}  # port -> latest complete distance vector
        self.distances = {addr: 0}
        self.forwarding = {}  # destination -> outgoing port

    INFINITY = 16

    def _recompute(self):
        distances = {self.addr: 0}
        forwarding = {}
        for port, (endpoint, cost) in sorted(self.neighbors.items()):
            candidates = {endpoint: 0}
            candidates.update(self.received.get(port, {}))
            for destination, advertised in candidates.items():
                if destination == self.addr:
                    continue
                distance = min(self.INFINITY, cost + advertised)
                if distance < distances.get(destination, self.INFINITY):
                    distances[destination] = distance
                    forwarding[destination] = port
        changed = distances != self.distances or forwarding != self.forwarding
        self.distances = distances
        self.forwarding = forwarding
        return changed

    def _advertise(self):
        for port, (endpoint, _) in self.neighbors.items():
            vector = {
                destination: (
                    self.INFINITY if self.forwarding.get(destination) == port
                    else distance
                )
                for destination, distance in self.distances.items()
            }
            self.send(port, Packet(Packet.ROUTING, self.addr, endpoint, dumps(vector)))

    def handle_packet(self, port, packet):
        """Process incoming packet."""
        if packet.is_traceroute:
            outgoing = self.forwarding.get(packet.dst_addr)
            if outgoing is not None:
                self.send(outgoing, packet)
        elif packet.is_routing and port in self.neighbors:
            endpoint, _ = self.neighbors[port]
            if packet.src_addr != endpoint:
                return
            vector = loads(packet.content)
            if vector != self.received.get(port):
                self.received[port] = vector
                if self._recompute():
                    self._advertise()

    def handle_new_link(self, port, endpoint, cost):
        """Handle new link."""
        self.neighbors[port] = (endpoint, cost)
        self.received.pop(port, None)
        self._recompute()
        self._advertise()

    def handle_remove_link(self, port):
        """Handle removed link."""
        self.neighbors.pop(port, None)
        self.received.pop(port, None)
        if self._recompute():
            self._advertise()

    def handle_time(self, time_ms):
        """Handle current time."""
        if time_ms - self.last_time >= self.heartbeat_time:
            self.last_time = time_ms
            self._advertise()

    def __repr__(self):
        """Representation for debugging in the network visualizer."""
        return f"DVrouter(addr={self.addr}, distances={self.distances})"
