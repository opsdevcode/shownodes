# Map of known (AZ name, account name) -> AZ ID values
AZ_MAP = {
    "us-east-1a": {
        "core-otto": "use1-az1",
        "platform-dev": "use1-az1",
        "platform-prod": "use1-az4",
        "platform-sandbox": "use1-az6",
        "platform-staging": "use1-az2",
    },
    "us-east-1b": {
        "core-otto": "use1-az2",
        "platform-dev": "use1-az2",
        "platform-prod": "use1-az6",
        "platform-sandbox": "use1-az1",
        "platform-staging": "use1-az4",
    },
    "us-east-1c": {
        "core-otto": "use1-az4",
        "platform-dev": "use1-az4",
        "platform-prod": "use1-az1",
        "platform-sandbox": "use1-az2",
        "platform-staging": "use1-az6",
    },
}


def az_pretty(az, mode: str = "name", account_name=str | None):
    """
    Prettify the AZ name. Usually by removing the region name. Mode options
    include `name` (or `az`), `id`, or a CSV-combined list.
    """
    mode = (mode or "name").lower()
    if mode and "," in mode:
        return " ".join(az_pretty(az, m, account_name) for m in mode.split(","))
    match mode:
        case "id":
            zone_ids = AZ_MAP.get(az)
            if not zone_ids:
                return "??"
            zoneid = zone_ids.get(account_name)
            if not zoneid:
                return "??"
            return zoneid[-3:]
        case "both":
            return az_pretty(az, "name,id", account_name)
        case "name" | "az" | None:
            return az[-2:]
        case _:
            raise ValueError(f"Unknown mode: {mode}")
