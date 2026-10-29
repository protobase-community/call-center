import json
from pathlib import Path

import pytest
from livekit import api

from agent_name import AGENT_NAME
from sip_setup import (
    apply,
    check_address,
    check_rule,
    check_trunk,
    load_rule,
    load_trunk,
    setup,
)

SIP_DIR = Path(__file__).parent.parent / "sip"


class FakeSip:
    def __init__(self):
        self.trunks: dict[str, api.SIPInboundTrunkInfo] = {}
        self.rules: dict[str, api.SIPDispatchRuleInfo] = {}
        self.writes: list[str] = []

    async def list_inbound_trunk(self, list):
        return api.ListSIPInboundTrunkResponse(items=self.trunks.values())

    async def create_inbound_trunk(self, create):
        self.writes.append("create_inbound_trunk")
        return self._save_trunk(f"ST_{len(self.trunks) + 1}", create.trunk)

    async def update_inbound_trunk(self, trunk_id, trunk):
        self.writes.append("update_inbound_trunk")
        return self._save_trunk(trunk_id, trunk)

    async def list_dispatch_rule(self, list):
        return api.ListSIPDispatchRuleResponse(items=self.rules.values())

    async def create_dispatch_rule(self, create):
        self.writes.append("create_dispatch_rule")
        return self._save_rule(f"SDR_{len(self.rules) + 1}", create.dispatch_rule)

    async def update_dispatch_rule(self, rule_id, rule):
        self.writes.append("update_dispatch_rule")
        return self._save_rule(rule_id, rule)

    def _save_trunk(self, trunk_id, trunk):
        saved = api.SIPInboundTrunkInfo()
        saved.CopyFrom(trunk)
        saved.sip_trunk_id = trunk_id
        self.trunks[trunk_id] = saved
        return saved

    def _save_rule(self, rule_id, rule):
        saved = api.SIPDispatchRuleInfo()
        saved.CopyFrom(rule)
        saved.sip_dispatch_rule_id = rule_id
        self.rules[rule_id] = saved
        return saved


def make_trunk(name="trunk", auth_username="user", auth_password="pass", **fields):
    return api.SIPInboundTrunkInfo(
        name=name, auth_username=auth_username, auth_password=auth_password, **fields
    )


def make_rule(name="per-call", **fields):
    individual = api.SIPDispatchRuleIndividual(room_prefix="call-")
    rule = api.SIPDispatchRule(dispatch_rule_individual=individual)
    return api.SIPDispatchRuleInfo(name=name, rule=rule, **fields)


async def test_creates_then_updates_the_same_records():
    sip = FakeSip()

    first = await apply(sip, make_trunk(), make_rule())
    second = await apply(sip, make_trunk(auth_password="other"), make_rule())

    assert first == {
        "trunk": {"id": "ST_1", "created": True},
        "dispatch_rule": {"id": "SDR_1", "created": True},
    }
    assert second == {
        "trunk": {"id": "ST_1", "updated": True},
        "dispatch_rule": {"id": "SDR_1", "updated": True},
    }
    assert sip.trunks["ST_1"].auth_password == "other"
    assert len(sip.trunks) == 1 and len(sip.rules) == 1


async def test_scopes_the_rule_to_the_trunk():
    sip = FakeSip()

    await apply(sip, make_trunk(), make_rule())

    assert list(sip.rules["SDR_1"].trunk_ids) == ["ST_1"]


async def test_rescopes_its_own_unscoped_rule():
    sip = FakeSip()
    sip._save_rule("SDR_9", make_rule())

    await apply(sip, make_trunk(), make_rule())

    assert list(sip.rules["SDR_9"].trunk_ids) == ["ST_1"]


async def test_refuses_to_run_next_to_a_rule_for_every_trunk():
    sip = FakeSip()
    sip._save_rule("SDR_9", make_rule(name="wild"))

    with pytest.raises(ValueError, match="SDR_9"):
        await apply(sip, make_trunk(), make_rule())

    assert sip.writes == []
    assert sip.trunks == {}


async def test_accepts_other_rules_scoped_to_other_trunks():
    sip = FakeSip()
    sip._save_rule("SDR_9", make_rule(name="other", trunk_ids=["ST_other"]))

    await apply(sip, make_trunk(), make_rule())

    assert list(sip.rules["SDR_2"].trunk_ids) == ["ST_1"]
    assert list(sip.rules["SDR_9"].trunk_ids) == ["ST_other"]


async def test_refuses_duplicate_names_without_writing():
    sip = FakeSip()
    sip._save_trunk("ST_8", make_trunk())
    sip._save_trunk("ST_9", make_trunk())

    with pytest.raises(ValueError, match="2 trunks"):
        await apply(sip, make_trunk(), make_rule())

    sip = FakeSip()
    sip._save_rule("SDR_8", make_rule(trunk_ids=["ST_1"]))
    sip._save_rule("SDR_9", make_rule(trunk_ids=["ST_1"]))

    with pytest.raises(ValueError, match="2 dispatch rules"):
        await apply(sip, make_trunk(), make_rule())

    assert sip.writes == []


@pytest.mark.parametrize(
    "trunk",
    [
        make_trunk(auth_password=""),
        make_trunk(auth_username=""),
        make_trunk(auth_username="", auth_password=""),
        make_trunk(auth_username="", auth_password="", allowed_addresses=["203.0.113.5"]),
        make_trunk(auth_username="", auth_password="", numbers=["+15550100"]),
    ],
)
def test_refuses_trunks_without_digest_auth(trunk):
    with pytest.raises(ValueError, match="auth_username and auth_password"):
        check_trunk(trunk)


def test_refuses_a_trunk_with_an_id():
    with pytest.raises(ValueError, match="sip_trunk_id"):
        check_trunk(make_trunk(sip_trunk_id="ST_1"))


def test_refuses_a_rule_with_trunk_ids_or_an_id():
    with pytest.raises(ValueError, match="trunk_ids"):
        check_rule(make_rule(trunk_ids=["ST_1"]))
    with pytest.raises(ValueError, match="sip_dispatch_rule_id"):
        check_rule(make_rule(sip_dispatch_rule_id="SDR_1"))


@pytest.mark.parametrize(
    "entry",
    [
        "sip.example.com",
        "203.0.113.5,203.0.113.6",
        "203.0.113.5 ",
        "10.0.0.0/255.0.0.0",
        "fe80::1%eth0",
        "fe80::1%eth0/64",
        "[::1]",
        "0.0.0.0/0",
        "::/0",
        "10.0.0.0/08",
        "203.0.113.0/33",
        "2001:db8::/129",
        "203.0.113.0/",
        "",
    ],
)
def test_refuses_addresses_livekit_does_not_match_by_ip(entry):
    with pytest.raises(ValueError, match="allowed_addresses"):
        check_address(entry)
    with pytest.raises(ValueError, match="allowed_addresses"):
        check_trunk(make_trunk(allowed_addresses=["203.0.113.9", entry]))


@pytest.mark.parametrize("entry", ["203.0.113.5", "203.0.113.0/24", "2001:db8::/32", "::1/128"])
def test_accepts_addresses_and_prefixes(entry):
    check_trunk(make_trunk(allowed_addresses=[entry]))


@pytest.mark.parametrize(
    ("trunk", "rule"),
    [
        ({"name": "trunk", "auth_username": "user"}, {"name": "per-call"}),
        (
            {"name": "trunk", "auth_username": "user", "auth_password": "pass"},
            {"name": "per-call", "trunk_ids": ["ST_1"]},
        ),
    ],
)
async def test_a_refused_file_writes_nothing(tmp_path, trunk, rule):
    sip = FakeSip()
    (tmp_path / "trunk.json").write_text(json.dumps(trunk))
    (tmp_path / "rule.json").write_text(json.dumps(rule))

    with pytest.raises(ValueError):
        await setup(sip, str(tmp_path / "trunk.json"), str(tmp_path / "rule.json"))

    assert sip.writes == []


async def test_setup_applies_the_files():
    sip = FakeSip()

    changed = await setup(
        sip, str(SIP_DIR / "inbound-trunk.json"), str(SIP_DIR / "dispatch-rule.json")
    )

    assert changed["trunk"] == {"id": "ST_1", "created": True}
    assert list(sip.rules["SDR_1"].trunk_ids) == ["ST_1"]


def test_repository_files_pass_their_checks():
    trunk = load_trunk(str(SIP_DIR / "inbound-trunk.json"))
    rule = load_rule(str(SIP_DIR / "dispatch-rule.json"))

    check_trunk(trunk)
    check_rule(rule)
    assert not trunk.numbers
    assert rule.rule.dispatch_rule_individual.room_prefix == "call-"
    assert [agent.agent_name for agent in rule.room_config.agents] == [AGENT_NAME]
