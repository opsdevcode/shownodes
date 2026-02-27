# import importlib.resources as ilib
# import importlib_resources as ilib
import json
from importlib.resources import files as import_files

import boto3

# TODO: decouple from us-east-1 default region
session = boto3.session.Session(region_name="us-east-1")
ec2 = session.client("ec2")

# hourly price information sourced from instances.vantage.sh
# # raw_price_data = importlib.resources.open_text("shownodes.data", "instance-prices.json")
raw_price_data = import_files("shownodes.data").joinpath("instance-prices.json").read_text()

prices = json.loads(raw_price_data)

# AWS provides a spot price history API, but the results of that API, at least
# when contacted through boto3, do not appear to be complete. For example, the
# spot prices available in some AZ may be unavailable, while there is good data
# available for sister AZs. In these cases it does not seem to help to walk back
# in time giving earlier StartTime and EndTime parameters (we've tried going
# back *months*, to no avail). So we use a hybrid strategy: Provide the desired
# AZ in the first query. If no results, then try again without the AZ parameter.
# This is slightly imprecise, but seems to give results within 2-3% of what
# AWS's `eks-node-viewer` tool reports. Good enough for an estimate.

# References:
# https://www.npmjs.com/package/aws-spot-price
# https://github.com/hoonoh/aws-spot-price/blob/master/src/lib/core.ts
# https://github.com/awslabs/eks-node-viewer/blob/main/pkg/pricing/pricing.go#L163


instance_price = {}  # cache of (instance_type, availability_zone) -> price


def get_spot_price(name: str, instance_type: str, availability_zone: str, timestamp, debug=False) -> float | None:
    """
    Given an instance type and availability zone, return the spot price. The instance's name
    and timestamp are used for debugging purposes only.
    """

    if debug:
        print(f"get_spot_price({name=}, {instance_type=}, {availability_zone=}, {timestamp=})")

    # first attempt to retrieve from cache
    cache_key = (instance_type, availability_zone)
    if cache_key in instance_price:
        return instance_price[cache_key]

    # not in cache; try to get price from AWS API with AZ parameter
    params = dict(
        InstanceTypes=[instance_type],
        ProductDescriptions=["Linux/UNIX"],
        AvailabilityZone=availability_zone,
    )
    try:
        response = ec2.describe_spot_price_history(**params)
        spot_price = float(response["SpotPriceHistory"][0]["SpotPrice"])
        instance_price[cache_key] = spot_price
        return spot_price
    except IndexError:  # most likely failure: no spot price data for this AZ
        pass

    # otherwise, try to get price from AWS *without* AZ parameter
    del params["AvailabilityZone"]
    try:
        response = ec2.describe_spot_price_history(**params)
        spot_price = float(response["SpotPriceHistory"][0]["SpotPrice"])
        instance_price[cache_key] = spot_price
        return spot_price
    except IndexError:  # most likely failure: no spot price data at all
        pass

    # could not find reasonable spot price data
    instance_price[cache_key] = None
    return None


def get_on_demand_price(
    name: str, instance_type: str, availability_zone: str, timestamp: str | None = None, debug=False
) -> float:
    """
    Given an instance type and availability zone, return the on-demand price. The instance's name
    and timestamp are used for debugging purposes only.
    """

    if debug:
        print(f"get_on_demand_price({name=}, {instance_type=}, {availability_zone=}, {timestamp=})")

    # first attempt to retrieve from cache
    # Convert availability_zone to region name by removing the trailing character if it is alphabetic
    region = availability_zone
    if region and region[-1].isalpha():
        region = region[:-1]
    cache_key = (instance_type, region)
    if cache_key in instance_price:
        if debug:
            print(f"Found in cache: {instance_price[cache_key]}")
        return instance_price[cache_key]

    from_data = prices.get(instance_type, {})
    if from_data:
        if debug:
            print(f"Found in data: {from_data}")
        from_data = float(from_data)
        instance_price[cache_key] = from_data
        return from_data

    try:
        result = get_ec2_ondemand_hourly_usd(instance_type, region)
    except Exception as e:
        result = 0.0
    instance_price[cache_key] = result
    return result


# Map EC2 region codes to the Pricing API's "location" strings
REGION_TO_LOCATION = {
    "us-east-1": "US East (N. Virginia)",
    "us-east-2": "US East (Ohio)",
    "us-west-2": "US West (Oregon)",
    "us-west-1": "US West (N. California)",
    # add more as needed
}


def get_ec2_ondemand_hourly_usd(
    instance_type: str,
    region_code: str,
    operating_system: str = "Linux",
    tenancy: str = "Shared",
    preinstalled_sw: str = "NA",
    capacitystatus: str = "Used",
) -> float:
    """
    Returns the EC2 On-Demand hourly price in USD for a given instance type + region + OS.
    Uses AWS Price List Query API (boto3 pricing.get_products). Note that this API hands back a complex
    structure including some unparsed JSON, and all of it is deeply nested and contorted by multiple
    layers of indirection and abstraction. We want a simple hourly price, but we have to wade through
    a complex price list, SKUs, offer terms, and price dimensions to get it.
    """
    if region_code not in REGION_TO_LOCATION:
        raise ValueError(f"Unknown region_code {region_code}. Add it to REGION_TO_LOCATION.")

    location = REGION_TO_LOCATION[region_code]

    # Pricing API is typically called in us-east-1 (endpoint region != compute region). :contentReference[oaicite:3]{index=3}
    pricing = boto3.client("pricing", region_name="us-east-1")

    filters = [
        {"Type": "TERM_MATCH", "Field": "instanceType", "Value": instance_type},
        {"Type": "TERM_MATCH", "Field": "location", "Value": location},
        {"Type": "TERM_MATCH", "Field": "operatingSystem", "Value": operating_system},
        {"Type": "TERM_MATCH", "Field": "tenancy", "Value": tenancy},
        {"Type": "TERM_MATCH", "Field": "preInstalledSw", "Value": preinstalled_sw},
        {"Type": "TERM_MATCH", "Field": "capacitystatus", "Value": capacitystatus},
        {"Type": "TERM_MATCH", "Field": "licenseModel", "Value": "No License required"},
    ]

    resp = pricing.get_products(
        ServiceCode="AmazonEC2",
        Filters=filters,
        FormatVersion="aws_v1",
        MaxResults=1,
    )

    price_list_str = resp.get("PriceList")
    # convert raw embedded JSON to a Python object
    price_list = json.loads(price_list_str[0])
    terms = price_list.get("terms")
    on_demand = terms.get("OnDemand")
    # get the first (and only) SKU - we're not wading through multiple SKUs here
    sku = next(iter(on_demand.keys()))
    offer = on_demand[sku]
    price_dimensions = offer.get("priceDimensions")
    for price_dimension in price_dimensions.values():
        if price_dimension.get("unit") == "Hrs":
            usd_str = price_dimension["pricePerUnit"]["USD"]
            return float(usd_str)
    # hmmm -- parsing failed in some way, or the API didn't return a price for what we wanted
    raise RuntimeError(f"No price found for {instance_type} {region_code} {operating_system} (filters too strict?)")


if __name__ == "__main__":
    price = get_ec2_ondemand_hourly_usd("m6a.2xlarge", "us-east-1", operating_system="Linux")
    print(price)  # Decimal('...')

# TODO: Consider if we should manage prices as float or Decimal
