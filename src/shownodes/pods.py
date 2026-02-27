import json
import os
from collections import Counter, defaultdict
from fnmatch import fnmatch

from .run import run
from .table import Header, print_table
from .time import format_age, human_duration


def get_pods(namespace=None) -> str:
    """
    Return a list of pods in the given namespace.
    """
    KUBECONFIG = os.environ["KUBECONFIG"]
    namespace_spec = f"-n {namespace}" if namespace else "-A"
    cmd = f"kubectl --kubeconfig={KUBECONFIG} get pods {namespace_spec} -o json"
    result = run(cmd)
    if result.stderr:
        print("ERROR: ", result.stderr)
    return json.loads(result.stdout)


def parse_pods(data: dict) -> dict:
    """
    Parse the output of get_pods() into a dict of node names -> pod info.
    """
    allpods = defaultdict(list)
    # Extract pod info, index by node name
    for item in data["items"]:
        name = item["metadata"]["name"]
        status = item["status"]["phase"]
        namespace = item["metadata"]["namespace"]
        nodename = item["spec"].get("nodeName", "<none>")
        timestamp = item["metadata"]["creationTimestamp"]
        age = human_duration(timestamp)
        podinfo = {
            "name": name,
            "status": status,
            "namespace": namespace,
            "nodename": nodename,
            "ip": item["status"].get("podIP", "??"),
            "timestamp": timestamp,
            "age": age,
        }
        if nodename == "NONE":
            print(f"WARNING: pod not running: {podinfo}")
        allpods[nodename].append(podinfo)
    # Sort pods by name
    for node, pods in allpods.items():
        pods.sort(key=lambda p: p["name"])
    return allpods


def pod_shortname(name: str) -> str:
    """
    Return a shortened version of the pod name (basically the kind of pod
    without the instance indentifying hashes).
    """

    parts = name.split("-")
    if len(parts) >= 3:
        return "-".join(parts[:-2])
    return "-".join(name.split("-")[:-1])


def parse_podspec(podspec: str) -> tuple[str, str, bool]:
    """
    Parse a pod spec string into a tuple of (pod-pattern, namespace-pattern).
    """
    if podspec.endswith("="):
        summary = False
        podspec = podspec[:-1]
    else:
        summary = True
    if ":" in podspec:
        podname, namespace = podspec.split(":")
    else:
        podname, namespace = podspec, "app"
    if not podname.endswith("*"):
        podname += "*"
    return podname, namespace, summary


def get_podextras(pod_record, names: list[str]) -> str:
    """
    Format the podextras needed for the given pod record.
    """
    if not names:
        return ""
    values = []
    for name in names:
        if name == "ns":
            name = "namespace"
        value = pod_record.get(name)
        if value is None:
            try:
                value = format_age(pod_record["timestamp"], name)
            except Exception:
                value = "??"
        values.append(value)
    return " ".join(values)


def formatted_count(count: int) -> str:
    return f" × {count}" if count > 1 else ""


def pod_displaylist(podinfo, nodename: str, podspec: str, extraspec: str) -> str:
    """
    Return a string with a list of pods running on the given node.
    """
    pod_pattern, ns_pattern, summary = parse_podspec(podspec)
    extras = extraspec.split(",") if extraspec else []

    podlist = [
        p
        for p in podinfo[nodename]
        if p["status"] == "Running" and fnmatch(p["name"], pod_pattern) and fnmatch(p["namespace"], ns_pattern)
    ]
    if summary:
        shortnames = sorted(pod_shortname(p["name"]) for p in podlist)
        counts = Counter(shortnames)
        return "\n".join(f"{name}{formatted_count(counts[name])}" for name in sorted(counts.keys()))
    else:
        return "\n".join([f'{p["name"]} {get_podextras(p, extras)}' for p in podlist])


def print_pod_summary(podinfo: dict) -> None:
    """
    Print a summary of the pods running in the cluster.
    """
    allpods = []
    for _, pods in podinfo.items():
        allpods.extend(pods)

    namespaces = Counter(p["namespace"] for p in allpods if p["status"] == "Running")
    print(f"{len(namespaces)} namespaces, {len(allpods)} pods")

    # show pod types running in each namespace
    rows = []
    for ns, count in sorted(namespaces.items()):
        podtypes = Counter(pod_shortname(p["name"]) for p in allpods if p["namespace"] == ns)
        extras = "\n".join(f"{name}{formatted_count(count)}" for name, count in sorted(podtypes.items()))
        rows.append([ns, count, extras])

    # Not 100% suitable to use print_table since it's customized for and specific to shownodes' main table...
    # but it kinda works and saves effort, so damn the torpedoes.
    print_table(rows, header=Header("Namespace Pods Extra"), footer=None)

    print()
