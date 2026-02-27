"""
Representation of a kubernetes node.
"""

import datetime as dt
import json
import os
import sys
from functools import cached_property
from pathlib import Path
from typing import Any

import arrow

from .access import access
from .base import DAYS_PER_MONTH, _global, as_int, divide_maybe, float_maybe
from .nodeprices import get_on_demand_price, get_spot_price
from .run import run


def error_exit(msg: str) -> None:
    if msg:
        print(msg)
    print(f"Try set-clus <cluster-name> first")
    exit(1)


def get_raw_node_info(data_file=None) -> str:
    """
    Return raw node info from kubectl, in JSON format, that can be parsed and displayed.
    Two major modes:
    1. Externally provided. `show-nodes` a bash function may pipe `kubectl get nodes -o json` to `shownodes`
    2. Standalone / internally sourced. `shownodes` the Python executable is run directly, and is responsible for getting its own
        data, either from a `kubectl` subshell or a data file.
    """
    if data_file:
        # if data file specified, get data from it (generally for testing)
        file_path = Path(data_file)
        with open(data_file) as f:
            raw = f.read()

        # adjust NOW to match the file's modification time (for consistent output)
        modification_timestamp = file_path.stat().st_mtime
        modification_datetime = dt.datetime.fromtimestamp(modification_timestamp)
        now = arrow.get(modification_datetime)
        _global.NOW = now
        return raw

    elif sys.stdin.isatty():
        # shownodes standalone execution from terminal - call kubectl subshell
        KUBECONFIG = os.environ["KUBECONFIG"]
        config_path = Path(KUBECONFIG)
        if not config_path.exists():
            error_exit(f"ERROR: KUBECONFIG file not doesn't exist at {KUBECONFIG}")
        cmd = f"kubectl --kubeconfig={KUBECONFIG} get nodes -o json"
        result = run(cmd)
        raw = result.stdout.strip()
        if result.stderr:
            if (
                "The connection to the server localhost:8080 was refused - did you specify the right host or port?"
                in result.stderr
            ):
                error_exit("Can't connect to cluster.")
            error_exit(f"ERROR: {result.stderr}")
        elif not raw:
            error_exit("ERROR: no data available")
        return raw

    else:
        # get data from stdin (piped in from external source, via show-nodes)
        raw = sys.stdin.read()
        if not raw.strip():
            error_exit("ERROR: no data provided via stdin")
        return raw


class Node(object):
    def __init__(self, nodeobj: dict | None) -> None:
        self.nodeobj = nodeobj or {}
        self.pods = None

    def access(self, path: str) -> Any:
        return access(self.nodeobj, path)

    @cached_property
    def nodename(self):
        return self.access(".metadata.name")

    @cached_property
    def capacity_type(self) -> str:
        """
        Get the type of capacity used. One of spot, on-demand, or fargate, with
        the first two possibly prefixed with NG/ to designate a managed node group.
        """
        ctype = self.access('.metadata.labels."karpenter.sh/capacity-type"')
        if not ctype:
            # non-Karpenter capacity type; fall back to EKS capacity type
            ctype = self.access('.metadata.labels."eks.amazonaws.com/capacityType"')
            if ctype:
                ctype = ctype.replace("_", "-").lower()
            else:
                # if not managed node group, likely Fargate
                ctype = self.access('.metadata.labels."eks.amazonaws.com/compute-type"')
        return ctype

    @cached_property
    def captype(self) -> str:
        """
        Humanized combination of capacity type and node group.
        """
        if self.is_in_nodegroup:
            return f"NG/{self.capacity_type}"
        return self.capacity_type

    @cached_property
    def is_in_nodegroup(self) -> bool:
        """
        Return True if this node is in a managed node group.
        """
        ng = self.access('.metadata.labels."eks.amazonaws.com/nodegroup"')
        return bool(ng)

    @cached_property
    def is_fargate(self) -> bool:
        """
        Return True if this node is a Fargate node.
        """
        return self.nodename.startswith("fargate")

    @cached_property
    def mem(self) -> int:
        """
        Get memory of node in GiB.
        """
        if self.is_in_nodegroup or self.is_fargate:
            mem = self.access(".status.capacity.memory")
            if mem.endswith("Ki"):
                mem = as_int(mem.replace("Ki", "")) / 1024  # convert into MiB
        else:
            mem = self.access('.metadata.labels."karpenter.k8s.aws/instance-memory"')
        return int(round(as_int(mem) / 1024))

    @cached_property
    def cpu(self) -> int:
        """
        Get CPU of node in vCPUs.
        """
        if self.is_in_nodegroup or self.is_fargate:
            cpu = self.access(".status.capacity.cpu")
        else:
            cpu = self.access('.metadata.labels."karpenter.k8s.aws/instance-cpu"')
        try:
            return int(cpu)
        except ValueError:
            return 0

    @cached_property
    def instance_id(self) -> str:
        provider_id = self.access(".spec.providerID")
        return provider_id.split("/")[-1]

    @cached_property
    def instance_type(self) -> str:
        return self.access('.metadata.labels."node.kubernetes.io/instance-type"') or self.access(
            '.metadata.labels."beta.kubernetes.io/instance-type"'
        )

    @cached_property
    def timestamp(self) -> str:
        return self.access(".metadata.creationTimestamp")

    @cached_property
    def arch(self) -> str:
        return self.access('.metadata.labels."beta.kubernetes.io/arch"')

    @cached_property
    def zone(self) -> str:
        return self.access('.metadata.labels."topology.kubernetes.io/zone"')

    @cached_property
    def images(self) -> list:
        return self.access(".status.images")

    @cached_property
    def image_size(self) -> int:
        return sum(i["sizeBytes"] for i in self.images)
        #  image_sizes.update({best_image_name(i): i["sizeBytes"] for i in imagelist})

    @cached_property
    def image_count(self) -> int:
        return len(self.images)

    @cached_property
    def status(self) -> str:
        """
        Return csv string of condition types that are True. If the unschedulable flag is true,
        add "NoSchedule" to the list. This mirrors the logic in kubectl.
        """
        raw_conditions = self.access(".status.conditions")
        unschedulable = self.access(".spec.unschedulable")
        conf_flags = [c["type"] for c in raw_conditions if c["status"] == "True"]
        if unschedulable:
            conf_flags.append("NoSchedule")
        return ",".join(conf_flags)

    @cached_property
    def standard_price(self) -> float | None:
        """
        Return the standard (on-demand) price of the node in $/hr.
        """
        return get_on_demand_price(self.nodename, self.instance_type, self.zone, self.timestamp)

    @cached_property
    def price(self) -> float | None:
        """
        Return the best known price for a node
        """
        if self.is_fargate:
            return None
        elif self.capacity_type == "spot":
            return get_spot_price(self.nodename, self.instance_type, self.zone, self.timestamp)
        else:
            return self.standard_price

    @cached_property
    def price_percent(self) -> float | None:
        """
        Return percentage of standard price the current price represents.
        """
        try:
            return self.price / self.standard_price
        except Exception:
            return None

    @cached_property
    def version(self) -> str:
        """
        Return the version of the node.
        """
        return self.access(".status.nodeInfo.kubeletVersion")


class NoNode(Node):
    """
    Class standing for node-like properties of the cluster itself,
    especially pods that have yet to be scheduled to an actual node.
    Should be singleton per cluster.
    """

    @cached_property
    def nodename(self):
        return "<none>"

    @cached_property
    def capacity_type(self) -> str:
        return "imaginary"

    @cached_property
    def is_in_nodegroup(self) -> bool:
        return False

    @cached_property
    def is_fargate(self) -> bool:
        return False

    @cached_property
    def mem(self) -> int:
        return 0

    @cached_property
    def cpu(self) -> int:
        return 0

    @cached_property
    def instance_id(self) -> str:
        return ""

    @cached_property
    def instance_type(self) -> str:
        return ""

    @cached_property
    def timestamp(self) -> str:
        return arrow.get(_global.NOW).isoformat()

    @cached_property
    def arch(self) -> str:
        return ""

    @cached_property
    def zone(self) -> str:
        return ""

    @cached_property
    def images(self) -> list:
        return []

    @cached_property
    def image_size(self) -> int:
        return 0

    @cached_property
    def image_count(self) -> int:
        return 0

    @cached_property
    def status(self) -> str:
        return "Ephemeral"

    @cached_property
    def standard_price(self) -> float | None:
        return None

    @cached_property
    def price(self) -> float | None:
        return None

    @cached_property
    def price_percent(self) -> float | None:
        return None

    @cached_property
    def version(self) -> str:
        rawdata = run("kubectl version").stdout
        jsondata = json.loads(rawdata)
        return jsondata["serverVersion"]["gitVersion"].split("-")[0]


class NodesSummary:
    def __init__(self, nodes):
        self.nodes = nodes

    @cached_property
    def count(self):
        return len(self.nodes)

    @cached_property
    def cpu(self):
        return sum(n.cpu for n in self.nodes)

    @cached_property
    def mem(self):
        return sum(n.mem for n in self.nodes)

    @cached_property
    def price(self):
        return sum(float_maybe(n.price) for n in self.nodes)

    @cached_property
    def standard_price(self):
        return sum(float_maybe(n.standard_price) for n in self.nodes)

    @cached_property
    def monthly_price(self):
        return self.price * 24 * DAYS_PER_MONTH

    @cached_property
    def price_percent(self):
        return divide_maybe(self.price, self.standard_price)


def get_nodes(data_file: str | None = None) -> list[Node]:
    """
    Return a list of node data objects, one for each node in the cluster.
    """
    raw = get_raw_node_info(data_file)
    return [Node(item) for item in json.loads(raw)["items"]]
