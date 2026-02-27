"""
Module to access the information kubectl reports (generally in JSON format).
"""


class NoSuchValue:
    pass


def path_to_parts(path: str) -> list[str]:
    """
    Given a path of JSON object parts as might appear in kubectl -o json output,
    return list of the parts. Note that some of the components might have
    quotes protecting internal dots.

    path_to_parts('.metadata.labels."node.kubernetes.io/instance-type"') ==
    ['metadata', 'labels', 'node.kubernetes.io/instance-type']
    """
    parts = []
    unquoted = path.split('"')
    for uq in unquoted:
        if not uq:
            continue
        elif uq.startswith("."):
            parts.extend(part for part in uq.split(".") if part)
        else:
            parts.append(uq)
    return parts


def access(obj, path):
    """
    Given a JSON object and a path of JSON object parts as might appear in
    kubectl -o json output, return the value at that path. If the path does not
    exist, return the empty string. If the path exists but the value is None,
    return the string 'null'.
    """
    parts = path_to_parts(path)
    for p in parts:
        obj = obj.get(p, NoSuchValue)
        if obj is NoSuchValue:
            return ""
        elif obj is None:
            return "null"
    return obj
