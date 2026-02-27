# shownodes

Enhanced `kubectl get nodes`.

Uses information from `kubectl get nodes` and `kubectl get pods` commands to
provide higher-value, more correlated output for better operational and
situational awareness.

* Describes the CPU architecture (e.g. 'amd64')
* Describes the resources available to each node (e.g. CPU, RAM)
* Knows the price of AWS instances and uses to provide cost info
* Dynamically looks up spot pricing for spot nodes, or estimates if not
  currently available.

Estimates the price of each node and of the cluster as a whole, using static
on-demand pricing. Gives a reasonable sense of how spendy a cluster
configuration could be.

## Options

`--sort-by=cpu,-mem` Can sort columns ascending (default) or descending (use `-`
prefix)

`--name=id,name` Shows name as instance id and standard nodename. Can also show
raw `ip` address. `dns` is a synonym for `name` (aka standard "node name").

`--az=name,id` Shows Availability Zone by both name and id (useful for physical
data center correlation).

`--age=edt,age` Shows node ages in US/Eastern timezone and age. Options are
humanized `age`, `k8s` version of humanized age, standard US timezones (e.g.
EDT, EST, PDT, ...), UTC/GMT/zulu standard time zone, Unix or Epoch (seconds
since the Unix epoch), and `iso` (RFC 3339/ISO 8601 standard timestamp in UTC).
Each of these is convenient for correlating with various other data sources.

`--pods=app` Shows where all the app pods live. By default shows abbreviated pod
names. End the query with an `=` to see the full pod names. Query expression
allows selecting pods and namespaces, e.g. `--pods=:*=` for all namespaces, or
`--pods=coredns:*` for all `coredns` pods. The `app` namespace is a default,
same as in Geodesic with `set-clus`.

`--status=Ready` Shows only Ready nodes.

`--status=-NoSched` Shows nodes omitting NoSchedule nodes.

`--stranded` Show special summary of "stranded" (waiting to terminate) nodes.

`--summary` Shows extended summary of pods in the cluster.

`--export` Exports CSV of currnet configuration

`--top` Add top information (CPU and MEM percent used)

`--highlight=<phrase>` Highlights given phrase in the table like a highlighter pen. Commas in `<phrase>` signal alternation, so `--highlight=12xlarge,16xlarge` applies the same highlight color to either `12xlarge` or `16xlarge` nodes. Multiple `--highlight` options may be given. Note this is simple string search in each table row; beware linguistic coincidence (e.g. `64` will match `amd64` and `64` GiB RAM and nodes with `64` in their node names). By default highlights in yellow. If you wish a specific highlight color, you can name it like such: `shownodes --highlight=orange:NG --highlight=yellow:16xlarge`. The available colors are yellow, pink, green, blue, orange, and purple.
