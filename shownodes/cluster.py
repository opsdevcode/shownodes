import os
import re
from functools import cached_property

from kubernetes import config


class Cluster:
    def __init__(self):
        pass

    @cached_property
    def kubeconfig(self) -> str:
        return os.environ["KUBECONFIG"]

    @cached_property
    def active_context(self) -> str:
        contexts, active = config.list_kube_config_contexts()
        return active

    @cached_property
    def namespace(self) -> str:
        return self.active_context["context"].get("namespace", "default")

    @cached_property
    def arn(self) -> str:
        """
        ARN of this cluster. E.g. "arn:aws:eks:us-east-1:421215911414:cluster/3p-platform-use1-prod-eks-cluster"
        """
        return self.active_context["context"].get("cluster", "default")

    @cached_property
    def fullname(self) -> str:
        """
        Full name of this cluster. E.g. "3p-platform-use1-prod-eks-cluster"
        """
        return self.arn.split("/")[-1]

    @cached_property
    def name(self) -> str:
        """
        Conventional name of this cluster. E.g. "platform-use1-prod"
        """
        try:
            return self.fullname.replace("3p-", "").replace("-eks-cluster", "")
        except Exception:
            return "???"

    @cached_property
    def account_name(self) -> str:
        """
        Acquire account name from cluster name.
        # e.g. "platform-use1-prod" -> "platform-prod"
        """
        return re.sub(r"-\w\w\w\d-", "-", self.name)
