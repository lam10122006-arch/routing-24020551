####################################################
# LSrouter.py
# Name:
# HUID:
#####################################################

from heapq import heappop, heappush
from json import dumps, loads

from packet import Packet
from router import Router


class LSrouter(Router):
    """Link state routing protocol implementation.

    Add your own class fields and initialization code (e.g. to create forwarding table
    data structures). See the `Router` base class for docstrings of the methods to
    override.
    """

    def __init__(self, addr, heartbeat_time):
        Router.__init__(self, addr)  # Initialize base class - DO NOT REMOVE
        self.heartbeat_time = heartbeat_time
        self.last_time = 0
        self.neighbors = {}  # port -> (endpoint, outgoing cost)
        self.sequence = 0
        self.link_states = {}  # origin -> (sequence, complete adjacency)
        self.forwarding = {}  # destination -> outgoing port

    def _local_links(self):
        links = {}
        for endpoint, cost in self.neighbors.values():
            if endpoint not in links or cost < links[endpoint]:
                links[endpoint] = cost
        return links

    def _flood(self, packet, incoming=None):
        for port in self.neighbors:
            if port != incoming:
                self.send(port, packet)

    def _publish(self):
        self.sequence += 1
        content = dumps({
            "origin": self.addr,
            "sequence": self.sequence,
            "links": self._local_links(),
        })
        self._flood(Packet(Packet.ROUTING, self.addr, self.addr, content))

    def _recompute(self):
        graph = {
            origin: links for origin, (_, links) in self.link_states.items()
        }
        graph[self.addr] = self._local_links()
        distances = {self.addr: 0}
        first_ports = {}
        pending = [(0, self.addr)]
        while pending:
            distance, origin = heappop(pending)
            if distance != distances[origin]:
                continue
            for endpoint, cost in graph.get(origin, {}).items():
                if origin == self.addr:
                    ports = [
                        port for port, (neighbor, _) in self.neighbors.items()
                        if neighbor == endpoint
                    ]
                    if not ports:
                        continue
                    first_port = min(ports, key=lambda port: (self.neighbors[port][1], port))
                else:
                    first_port = first_ports[origin]
                candidate = distance + cost
                if candidate < distances.get(endpoint, float("inf")):
                    distances[endpoint] = candidate
                    first_ports[endpoint] = first_port
                    heappush(pending, (candidate, endpoint))
        self.forwarding = first_ports

    def handle_packet(self, port, packet):
        """Process incoming packet."""
        if packet.is_traceroute:
            outgoing = self.forwarding.get(packet.dst_addr)
            if outgoing is not None:
                self.send(outgoing, packet)
        elif packet.is_routing and port in self.neighbors:
            update = loads(packet.content)
            origin = update["origin"]
            sequence = update["sequence"]
            if origin == self.addr or sequence <= self.link_states.get(origin, (0, {}))[0]:
                return
            self.link_states[origin] = (sequence, update["links"])
            self._recompute()
            self._flood(packet, incoming=port)

    def handle_new_link(self, port, endpoint, cost):
        """Handle new link."""
        self.neighbors[port] = (endpoint, cost)
        self._recompute()
        self._publish()

    def handle_remove_link(self, port):
        """Handle removed link."""
        self.neighbors.pop(port, None)
        self._recompute()
        self._publish()

    def handle_time(self, time_ms):
        """Handle current time."""
        if time_ms - self.last_time >= self.heartbeat_time:
            self.last_time = time_ms
            self._publish()

    def __repr__(self):
        """Representation for debugging in the network visualizer."""
        return f"LSrouter(addr={self.addr}, forwarding={self.forwarding})"
