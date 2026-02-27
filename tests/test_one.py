import pytest
from click.testing import CliRunner

from shownodes.cli import main, status_match


def _test_string(s):
    if s.startswith("\n\n"):
        s = s[1:]
    return s


def _result_string(s):
    lines = s.splitlines()
    return "\n".join([line.rstrip() for line in lines])


@pytest.mark.skip("integration")
def test_hello_world():
    runner = CliRunner()
    result = runner.invoke(main, ["--data-file=./tests/testdata/nodes_test_01.json", "--width=180"])
    assert result.exit_code == 0
    expected_result = _test_string(
        """

 NAME                           TYPE           $/HR    $%    ARCH   CPU  MEM  IMAGES  IMAGESIZE  AZ       CAPTYPE  AGE  STATUS
 ─────────────────────────────  ─────────────  ──────  ────  ─────  ───  ───  ──────  ─────────  ──  ────────────  ───  ────────────────
 ip-10-136-1-236.ec2.internal   c6in.2xlarge   0.454   100%  amd64    8   16      12          5  1a     on-demand   0d  Ready
 ip-10-136-18-178.ec2.internal  c6in.2xlarge   0.454   100%  amd64    8   16      13          7  1a     on-demand   4m  Ready
 ip-10-136-31-57.ec2.internal   c6in.8xlarge   1.814   100%  amd64   32   64      13          5  1a     on-demand   0d  Ready
 ip-10-136-35-5.ec2.internal    c6in.4xlarge   0.907   100%  amd64   16   32      12          5  1b     on-demand   0d  Ready
 ip-10-136-41-133.ec2.internal  m6in.16xlarge  4.455   100%  amd64   64  256      11          5  1b     on-demand   0d  Ready
 ip-10-136-52-189.ec2.internal  c6in.4xlarge   0.907   100%  amd64   16   32      11          5  1b     on-demand   0d  Ready,NoSchedule
 ip-10-136-72-140.ec2.internal  c6in.16xlarge  3.629   100%  amd64   64  128      50         50  1c     on-demand   6d  Ready
 ip-10-136-80-145.ec2.internal  c6in.xlarge    0.227   100%  amd64    4    8      23         25  1c  NG/on-demand   6d  Ready
 ─────────────────────────────  ─────────────  ──────  ────  ─────  ───  ───  ──────  ─────────  ──  ────────────  ───  ────────────────
 TOTAL                                         12.847  100%         212  552      55         50

cluster ??? at 2023-08-15T15:37:55Z: 8 working nodes, est $9326.92/month
"""
    )
    assert _result_string(result.output) == expected_result


"""
Current testing better than no testing, but remains fragile. Depends on
different generations of price data (from Vantage) plus various spot price data
responses, and plausibly on kubectl versions as well. Possible we could couple a
Vantage static data set, specific spot data seen, and note the kubectl version
in a data-gathering run that would then establish a future tests. But complex
data set and variable sources with end-to-end tests are not a good mix. Should
figure out how to mock key data or reduce test size.
"""


def test_status_match():
    assert status_match("Ready", "ready")
    assert status_match("Ready,NoSchedule", "ready")
    assert not status_match("NoSchedule", "ready")
    assert status_match("NoSchedule", "-ready")
