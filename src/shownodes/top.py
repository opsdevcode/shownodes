from decimal import Decimal, getcontext

from kubernetes import client, config
from kubernetes.client import CustomObjectsApi
from kubernetes.utils.quantity import parse_quantity

# Better precision for percentage math
getcontext().prec = 28


def get_node_top(use_allocatable=True) -> list[dict]:
    """
    Returns list of dicts: node, cpu_usage, cpu_total, cpu_pct, mem_usage, mem_total, mem_pct
    use_allocatable=True -> percentages relative to 'allocatable' (what pods can actually use)
    use_allocatable=False -> percentages relative to 'capacity' (node’s full capacity)
    """
    # Load kubeconfig (or use config.load_incluster_config() inside a pod)
    config.load_kube_config()

    v1 = client.CoreV1Api()
    co = CustomObjectsApi()

    # 1) Get node metrics (usage)
    try:
        m = co.list_cluster_custom_object("metrics.k8s.io", "v1beta1", "nodes")
    except Exception as e:
        print(f"Node metrics not available (no metrics server?)")
        return []
    usage_by_node = {}
    for item in m.get("items", []):
        name = item["metadata"]["name"]
        # Quantities like "123m" (CPU), "2048Mi" (memory)
        cpu_usage = Decimal(parse_quantity(item["usage"]["cpu"]))  # cores
        mem_usage = Decimal(parse_quantity(item["usage"]["memory"]))  # bytes
        usage_by_node[name] = (cpu_usage, mem_usage)

    # 2) Get node capacities / allocatables
    out = []
    for node in v1.list_node().items:
        name = node.metadata.name
        alloc = node.status.allocatable
        cap = node.status.capacity

        if not alloc or not cap or name not in usage_by_node:
            continue

        cpu_total = Decimal(parse_quantity((alloc if use_allocatable else cap)["cpu"]))  # cores
        mem_total = Decimal(parse_quantity((alloc if use_allocatable else cap)["memory"]))  # bytes

        cpu_usage, mem_usage = usage_by_node[name]

        # Avoid division by zero on weird nodes
        cpu_pct = (cpu_usage / cpu_total * 100) if cpu_total > 0 else Decimal(0)
        mem_pct = (mem_usage / mem_total * 100) if mem_total > 0 else Decimal(0)

        out.append(
            {
                "node": name,
                "cpu_usage_cores": float(cpu_usage),
                "cpu_total_cores": float(cpu_total),
                "cpu_pct": float(cpu_pct),
                "mem_usage_bytes": int(mem_usage),
                "mem_total_bytes": int(mem_total),
                "mem_pct": float(mem_pct),
                "basis": "allocatable" if use_allocatable else "capacity",
            }
        )

    # Sort like `kubectl top nodes` (descending CPU%)
    out.sort(key=lambda r: r["cpu_pct"], reverse=True)
    return out


def get_node_top_dict(use_allocatable=True) -> dict[str, dict]:
    """
    Returns a dictionary of node names to dicts: node, cpu_usage, cpu_total, cpu_pct, mem_usage, mem_total, mem_pct
    use_allocatable=True -> percentages relative to 'allocatable' (what pods can actually use)
    use_allocatable=False -> percentages relative to 'capacity' (node’s full capacity)
    """
    return {node["node"]: node for node in get_node_top(use_allocatable)}
