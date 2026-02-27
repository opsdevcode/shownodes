#!/usr/bin/env python3

"""
Operational helper to show kubernetes nodes in an infrastructure- and cost-
centered way more operationally helpful than mere `k get nodes`.

Uses Python rather than bash/Unix tools to post-process `kubectl get nodes -o json`
output for greater ease, reliability, and control.
"""

from collections import defaultdict
from math import ceil
from pprint import pprint
from typing import Any

import arrow
import click
from binary import BinaryUnits, convert_units
from rich import inspect

from .attrdict import AttrDict
from .azmap import az_pretty
from .base import DAYS_PER_MONTH, _global
from .cluster import Cluster
from .ip import canonical_ip
from .node import Node, NodesSummary, NoNode, get_nodes
from .output import Output, literal
from .pods import get_pods, parse_pods, pod_displaylist, print_pod_summary
from .table import (Header, export_table, print_table, row_highlighter,
                    sort_rows)
from .time import format_age, zulutime
from .top import get_node_top_dict
from .units import intGiB

opts = AttrDict()


def best_image_name(image_record: dict) -> str:
    """
    Given a dict representing a kubernetes image record, return the best
    name. For our purposes, the best name is the shortest one...ideally
    that will make it the most recognizable.
    """
    # Retrieve the names, sort by str length, return shortest name
    names = [(n, len(n)) for n in image_record["names"]]
    names.sort(key=lambda x: x[1])
    return names[0][0]


def plural(n, suffix="s"):
    return "" if n == 1 else suffix


def format_node_name(name: str, instance_id: str, mode: str | None = "name") -> str:
    """
    Format k8s node name. Generally is a long string like
    `ip-10-128-1-20.ec2.internal` however this is just an IP address wrapped in
    a DNS-compatible name. If mode == "ip" convert to the IP address. If mode ==
    "id" answer the instance id. Convenient for mapping directly to other data
    sources, such as Datadog.
    """
    if mode is not None and "," in mode:
        return " ".join(format_node_name(name, instance_id, m) for m in mode.split(","))
    match mode:
        case "ip":
            return canonical_ip(name)
        case "id":
            return instance_id
        case "name" | "dns" | _:
            return name


def print_standard_summary(all_nodes: bool, summary: NodesSummary, cluster_name: str) -> None:
    now_display = zulutime(_global.NOW.replace(microsecond=0))
    main_display = "working " if not opts.all_nodes else ""
    ey_hourly_cpu_price = 10.638
    ey_monthly_cpu_price = ey_hourly_cpu_price * 24 * DAYS_PER_MONTH
    cp_vs_ey = summary.monthly_price / ey_monthly_cpu_price
    ey_compare = f" ({cp_vs_ey:0.0%} EYΩ)" if "prod" in cluster_name else ""
    print(
        f"cluster {cluster_name} at {now_display}: "
        f"{summary.count} {main_display}node{plural(summary.count)}, "
        f"est ${summary.monthly_price:0,.2f}/month{ey_compare}"
    )


def print_scaled_summary(all_nodes: bool, summary: NodesSummary, cluster_name: str) -> None:
    """
    Print a scaled summary of the nodes in the cluster.
    """
    stage = cluster_name.split("-")[-1]
    match stage:
        case "dev":
            typical_cpu = 3 * 16
            typical_mem = 3 * 61
        case "prod":
            typical_cpu = 3 * 64
            typical_mem = 3 * 247
        case _:
            print("Only dev and prod clusters have fixed baselines for scaling factors")
            return

    # Compute current CPU and memory from the summary
    current_cpu = summary.cpu
    current_mem = summary.mem

    cpu_factor = current_cpu / typical_cpu if typical_cpu else 0
    mem_factor = current_mem / typical_mem if typical_mem else 0
    cpu_factor_str = f"{cpu_factor:.2f}"
    mem_factor_str = f"{mem_factor:.2f}"
    together_factor = (cpu_factor + mem_factor) / 2
    together_factor_str = f"{together_factor:.2f}"

    rows = [
        ["current", current_cpu, current_mem],
        ["typical", typical_cpu, typical_mem],
        None,
        ["factor", cpu_factor_str, mem_factor_str],
        ["~factor", together_factor_str, together_factor_str],
    ]
    header = Header(["", "CPU>", "MEM>"])

    print()
    print_table(rows, header, None, None, [])
    print()


def print_stranded_summary(nodes: list[Node], overall: NodesSummary) -> None:
    """
    Determine extend of "stranded" nodes: ones that are not currently schedulable
    (generally because they're waiting to be deprovisioned).
    """
    stranded_nodes = [n for n in nodes if "NoSchedule" in n.status]
    if stranded_nodes:
        stranded = NodesSummary(stranded_nodes)
        print(
            f"{stranded.count} 'stranded' node{plural(stranded.count)}, "
            f"{stranded.cpu} CPUs, "
            f"{stranded.mem} RAM, estimated ${stranded.price:0,.2f}/hour, "
            f"${stranded.monthly_price:0.2f}/month "
            f"({stranded.price / overall.price:0.0%} of total)"
        )
    else:
        print("no nodes currently stranded (i.e. cordoned and waiting for termination)")
    print()


def status_match(status: str, status_spec: str) -> bool:
    """
    Give a status CSV and a status specification (from opts.status),
    determine if they match.
    """
    negate = status_spec.startswith("-")
    wanted_status = status_spec.lower().lstrip("-")
    matching = wanted_status in status.lower()
    return (matching and not negate) or (negate and not matching)


HELP = AttrDict(
    age="Age of node: age,k8s,iso,unix|epoch,edt|<timezone>,zulu|gmt|utc",
    all_nodes="Also show Fargate nodes",
    az="Availability Zone: name,id",
    data_file="Path to JSON file to import nodes from",
    debug="Be excessively verbose",
    export="Export to CSV",
    highlight="Highlight matching strings in output. eg. --highlight=Ready or --highlight=pink:NoSched",
    name="How node is identified: name|dns,ip,id",
    pods="eg: --pods for current ns,--pods=:app or --pods=:coredns. Add trailing = to show verbosely.",
    podsextra="Extra pod info. choices: ns|namespace,ip,status,age (age can be replaced by any option for --age)",
    pricing="Show pricing information",
    scaled="Show scaled summary of nodes",
    sort_by="CSV of fields to sort, - to reverse. eg: --sort-by=-age,name",
    status="Node status to match, - to negate. E.g. --status=-Ready",
    stranded="Show summary of stranded nodes",
    summary="Show extended summary of pods",
    top="Show node CPU and memory usage",
    topplus="Top harder. Show net resources used.",
    version="Show k8s version",
    width="Set terminal width of display",
)

csv = dict(metavar="CSV")


@click.command(epilog="See README.md for more information.")
@click.option("--age", type=str, default="age", help=HELP.age, **csv)
@click.option("-a", "--all", "all_nodes", type=bool, default=False, is_flag=True, help=HELP.all_nodes)
@click.option("--az", type=str, default="az", help=HELP.az, **csv)
@click.option("--data-file", type=str, default=None, help=HELP.data_file)
@click.option("--debug", type=bool, default=False, is_flag=True, help=HELP.debug)
@click.option("--export", type=bool, default=False, is_flag=True, help=HELP.export)
@click.option("--highlight", type=str, default=None, multiple=True, help=HELP.highlight)
@click.option("--name", type=str, default="dns", help=HELP.name, **csv)
@click.option("--pods", "--pod", type=str, default=None, is_flag=False, flag_value="", help=HELP.pods)
@click.option("--podsextra", "--podextra", type=str, default="", help=HELP.podsextra, **csv)
@click.option("--sort-by", type=str, default=None, help=HELP.sort_by, **csv)
@click.option("--pricing", type=bool, default=False, is_flag=True, help=HELP.pricing)
@click.option("--scaled", type=bool, default=False, is_flag=True, help=HELP.scaled)
@click.option("--status", type=str, default="", help=HELP.status, **csv)
@click.option("--stranded", type=bool, default=False, is_flag=True, help=HELP.stranded)
@click.option("--summary", type=bool, default=False, is_flag=True, help=HELP.summary)
@click.option("--top/--no-top", is_flag=True, default=True, help=HELP.top)
@click.option("--topplus", "--top-plus", is_flag=True, help=HELP.topplus)
@click.option("--width", type=int, default=0, help=HELP.width)
@click.version_option()
def main(**kwargs):
    """
    Show kubernetes nodes in an infrastructure-informed and cost-centered way. Enhanced
    `kubectl get nodes` and `kubectl get pods` with more information, better formatting,
    and better correlation of relevant information.

    Useful examples:

    shownodes --sort-by=age

    shownodes --status=NoSched

    shownodes --name=id,name --az=name,id --age=k8s --pods=app

    shownodes --pods=coredns:*= --podsextra=ip,status,k8s,epoch,edt --width=0

    """
    opts.update(**kwargs)
    cluster = Cluster()

    if opts.pods is not None and opts.pods == "":
        opts.pods = f":{cluster.namespace}"
    nodes = get_nodes(opts.data_file)

    header = Header("NAME TYPE ARCH CPU> MEM> AZ CAPTYPE AGE> STATUS")
    if opts.pricing:
        header.follow("TYPE", ["$/HR>", "$%>"])
    if opts.topplus:
        opts.top = True
    if opts.top:
        top_dict = get_node_top_dict(use_allocatable=False)
        header.follow("CPU", "CPU%>")
        header.follow("MEM", "MEM%>")
        if opts.topplus:
            header.follow("CPU%", "CPU.>")
            header.follow("MEM%", "MEM.>")
    podinfo = {}
    if opts.pods or opts.summary:
        podinfo = parse_pods(get_pods())
        if opts.pods:
            header.follow("STATUS", "PODS")
            if unhomed := podinfo.get("<none>"):
                cluster_node = NoNode({})
                cluster_node.pods = unhomed
                nodes.insert(0, cluster_node)

    filtered_nodes = []

    rowdicts = []

    for N in nodes:
        if N.capacity_type == "fargate" and not opts.all_nodes:
            continue
        elif opts.status and not status_match(N.status, opts.status):
            continue

        row = defaultdict(lambda: "")
        row["NAME"] = format_node_name(N.nodename, N.instance_id, opts.name)
        row["TYPE"] = N.instance_type
        row["$/HR"] = Output(N.price, "0.3f")
        row["$%"] = Output(N.price_percent, "0.0%")
        row["ARCH"] = N.arch
        row["CPU"] = N.cpu
        row["MEM"] = N.mem
        row["AZ"] = az_pretty(N.zone, opts.az, cluster.account_name)
        row["CAPTYPE"] = N.captype
        row["AGE"] = Output(_global.NOW - arrow.get(N.timestamp), literal(format_age(N.timestamp, opts.age)))
        row["STATUS"] = N.status

        if opts.top:
            top_node = top_dict.get(N.nodename)
            if top_node:
                row["CPU%"] = f"{top_node["cpu_pct"]:.0f}"
                row["MEM%"] = f"{top_node["mem_pct"]:.0f}"
                if opts.topplus:
                    row["CPU."] = str(int(ceil(top_node["cpu_usage_cores"])))
                    row["MEM."] = str(int(ceil(top_node["mem_usage_bytes"] / 1024**3)))
            else:
                # if missing, add dummy values for best display and summ without errors
                row["CPU%"] = row["MEM%"] = row["CPU."] = row["MEM."] = "?"
                default = {"cpu_total_cores": 0, "cpu_usage_cores": 1, "mem_total_bytes": 0, "mem_usage_bytes": 1}
                top_dict.setdefault(N.nodename, default)
        if opts.pods:
            row["PODS"] = pod_displaylist(podinfo, N.nodename, opts.pods, opts.podsextra)
            N.pods = podinfo[N.nodename]
        filtered_nodes.append(N)
        rowdicts.append(row)

    summary = NodesSummary(filtered_nodes)

    footer = defaultdict(lambda: "")
    footer["NAME"] = "TOTAL"
    footer["$/HR"] = Output(summary.price, "0.3f")
    footer["$%"] = Output(summary.price_percent, "0.0%")
    footer["CPU"] = summary.cpu
    footer["MEM"] = summary.mem

    if opts.top:
        topped_nodes = [N.nodename for N in filtered_nodes]
        try:
            cpu_total_cores = sum(top_dict[node]["cpu_total_cores"] for node in topped_nodes)
            cpu_usage_cores = sum(top_dict[node]["cpu_usage_cores"] for node in topped_nodes)
            total_cpu_pct = 100.0 * cpu_usage_cores / cpu_total_cores
            mem_total_bytes = sum(top_dict[node]["mem_total_bytes"] for node in topped_nodes)
            mem_usage_bytes = sum(top_dict[node]["mem_usage_bytes"] for node in topped_nodes)
            total_mem_pct = 100.0 * mem_usage_bytes / mem_total_bytes
            total_cpu_pct_display = f"{total_cpu_pct:.0f}"
            total_mem_pct_display = f"{total_mem_pct:.0f}"
            mem_usage_gib = mem_usage_bytes / 1024**3
            footer["CPU%"] = total_cpu_pct_display
            footer["MEM%"] = total_mem_pct_display
        except Exception:
            total_cpu_pct_display = "?"
            total_mem_pct_display = "?"
        if opts.topplus:
            footer["CPU."] = str(int(ceil(cpu_usage_cores)))
            footer["MEM."] = str(int(ceil(mem_usage_gib)))

    # Now use headers to convert rowdicts into rows
    rows = []
    header_names = [h.name for h in header]
    for rd in rowdicts:
        rows.append([rd[hname] for hname in header_names])
    footer_row = [footer[hname] for hname in header_names]

    if opts.sort_by:
        rows = sort_rows(rows, opts.sort_by, header)

    print_table(rows, header, footer_row, opts.width, highlight=opts.highlight)

    print_standard_summary(opts.all_nodes, summary, cluster.name)

    if opts.scaled:
        print_scaled_summary(opts.all_nodes, summary, cluster.name)

    if opts.stranded:
        print_stranded_summary(nodes, summary)

    if opts.summary:
        print_pod_summary(podinfo)

    if opts.export:
        export_table(rows, header_names, footer_row, cluster.name)


if __name__ == "__main__":
    cli()


# TODO: More Cluster upleveling (locate .nodes, .pods, .images there)
# TODO: consider switching from BinaryUnits to pint for unit conversions (more flexible, less code)
# TODO: Pods and Nodes abstractions make sense
# TODO: consider objectifying TableType into real class
# TODO: consider upleveling interface to rich.table features
# TODO: image computation could especially be cleaned up
# TODO: should pods always be loaded? would allow a #pods field per node
