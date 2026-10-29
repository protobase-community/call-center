"""Creates or updates the inbound SIP trunk and its dispatch rule from two JSON files.

usage: sip_setup.py <trunk json> <rule json>

Records are matched by name, so a second run updates them in place and keeps their IDs.
It refuses setups that would let callers in without answering the trunk's digest challenge.
"""

import asyncio
import ipaddress
import json
import sys
from typing import Protocol

from google.protobuf import json_format
from livekit import api


class SipApi(Protocol):
    async def list_inbound_trunk(
        self, list: api.ListSIPInboundTrunkRequest
    ) -> api.ListSIPInboundTrunkResponse: ...

    async def create_inbound_trunk(
        self, create: api.CreateSIPInboundTrunkRequest
    ) -> api.SIPInboundTrunkInfo: ...

    async def update_inbound_trunk(
        self, trunk_id: str, trunk: api.SIPInboundTrunkInfo
    ) -> api.SIPInboundTrunkInfo: ...

    async def list_dispatch_rule(
        self, list: api.ListSIPDispatchRuleRequest
    ) -> api.ListSIPDispatchRuleResponse: ...

    async def create_dispatch_rule(
        self, create: api.CreateSIPDispatchRuleRequest
    ) -> api.SIPDispatchRuleInfo: ...

    async def update_dispatch_rule(
        self, rule_id: str, rule: api.SIPDispatchRuleInfo
    ) -> api.SIPDispatchRuleInfo: ...


def load_trunk(path: str) -> api.SIPInboundTrunkInfo:
    with open(path) as file:
        return json_format.ParseDict(json.load(file), api.SIPInboundTrunkInfo())


def load_rule(path: str) -> api.SIPDispatchRuleInfo:
    with open(path) as file:
        return json_format.ParseDict(json.load(file), api.SIPDispatchRuleInfo())


def check_address(entry: str) -> None:
    """Accepts only what LiveKit matches by IP: an address, or one with a prefix length.

    LiveKit drops invalid entries silently, matches everything when all are dropped, and
    compares other forms only with the caller-written From host.
    """
    if "%" in entry:
        raise ValueError(f"allowed_addresses entry {entry!r} has a zone")
    address, slash, bits = entry.partition("/")
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        raise ValueError(f"allowed_addresses entry {entry!r} is not an IP address") from None
    if not slash:
        return
    if not (bits.isdigit() and str(int(bits)) == bits and 1 <= int(bits) <= ip.max_prefixlen):
        raise ValueError(
            f"allowed_addresses entry {entry!r} needs a prefix length from 1 to {ip.max_prefixlen}"
        )


def check_trunk(trunk: api.SIPInboundTrunkInfo) -> None:
    # LiveKit challenges only when both are set, and allowed_addresses alone can be matched
    # by the caller's own From header, so digest is the only access control accepted.
    if not trunk.auth_username or not trunk.auth_password:
        raise ValueError("the trunk needs both auth_username and auth_password")
    if trunk.sip_trunk_id:
        raise ValueError("the trunk must not set sip_trunk_id")
    for entry in trunk.allowed_addresses:
        check_address(entry)


def check_rule(rule: api.SIPDispatchRuleInfo) -> None:
    if rule.trunk_ids:
        raise ValueError("the dispatch rule must not set trunk_ids: the setup scopes it")
    if rule.sip_dispatch_rule_id:
        raise ValueError("the dispatch rule must not set sip_dispatch_rule_id")


def one_named(records: list, name: str, kind: str):
    same = [record for record in records if record.name == name]
    if len(same) > 1:
        raise ValueError(f"{len(same)} {kind}s are named {name!r}")
    return same[0] if same else None


async def apply(sip: SipApi, trunk: api.SIPInboundTrunkInfo, rule: api.SIPDispatchRuleInfo) -> dict:
    trunks = (await sip.list_inbound_trunk(api.ListSIPInboundTrunkRequest())).items
    existing_trunk = one_named(list(trunks), trunk.name, "trunk")
    rules = (await sip.list_dispatch_rule(api.ListSIPDispatchRuleRequest())).items
    existing_rule = one_named(list(rules), rule.name, "dispatch rule")

    # LiveKit sends callers that match no trunk to rules without trunk IDs, unchallenged
    for other in rules:
        if other.name != rule.name and not other.trunk_ids:
            raise ValueError(
                f"dispatch rule {other.sip_dispatch_rule_id} ({other.name!r}) applies to every "
                "trunk, which admits callers that match no trunk: scope or delete it"
            )

    if existing_trunk:
        saved_trunk = await sip.update_inbound_trunk(existing_trunk.sip_trunk_id, trunk)
    else:
        saved_trunk = await sip.create_inbound_trunk(api.CreateSIPInboundTrunkRequest(trunk=trunk))

    rule.trunk_ids[:] = [saved_trunk.sip_trunk_id]
    if existing_rule:
        saved_rule = await sip.update_dispatch_rule(existing_rule.sip_dispatch_rule_id, rule)
    else:
        saved_rule = await sip.create_dispatch_rule(
            api.CreateSIPDispatchRuleRequest(dispatch_rule=rule)
        )

    return {
        "trunk": {
            "id": saved_trunk.sip_trunk_id,
            "updated" if existing_trunk else "created": True,
        },
        "dispatch_rule": {
            "id": saved_rule.sip_dispatch_rule_id,
            "updated" if existing_rule else "created": True,
        },
    }


async def setup(sip: SipApi, trunk_path: str, rule_path: str) -> dict:
    trunk = load_trunk(trunk_path)
    rule = load_rule(rule_path)
    check_trunk(trunk)
    check_rule(rule)
    return await apply(sip, trunk, rule)


async def main(trunk_path: str, rule_path: str) -> None:
    lkapi = api.LiveKitAPI()
    changed = await setup(lkapi.sip, trunk_path, rule_path)
    await lkapi.aclose()
    print(json.dumps(changed))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: sip_setup.py <trunk json> <rule json>")
    asyncio.run(main(sys.argv[1], sys.argv[2]))
