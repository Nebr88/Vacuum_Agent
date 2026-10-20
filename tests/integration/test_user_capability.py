"""Moving a capability flag from us to the person who can see the machine.

SOME CAPABILITIES WE DERIVE AND SOME WE GUESS, AND THEY WERE STORED AS THE SAME VALUE.
Roborock answers "can this vary its cleaning path?" from whether the device's own
mop-route select carries a usable value — that is knowledge. Eufy answered it with
`model_family in {"x10", "x8"}` — a conservative guess made when nobody had checked the
other models, standing in for knowledge that was never gathered. Read as a plain
boolean, the guess DENIES a control to hardware that may well have it.

So the flag moves to the user, with a third state for "nobody has established this".
A caller must test `is False` and offer the control otherwise; collapsing None to False
reinstates the exact defect.

The name is deliberately NOT `supports_path_control`. That one is read by
`dispatch/manager.py::dispatch_goto` as GO-TO support — "declares path control (go-to)
unsupported" — and Roborock had been populating it from the mop-route select, so an
unavailable select could have gated go-to. Inert today only because this brand declares
no goto service and the earlier guard catches first. Two capabilities, two names.

Coverage targets
----------------
[UC-1] nobody has answered and no brand derived one -> None, meaning "not established".
[UC-2] a brand's DERIVED answer is used when the user has not spoken.
[UC-3] the USER's answer wins over the derived one, in both directions.
[UC-4] clearing the answer hands the question back to detection — a wrong answer is
       never a trap.
[UC-5] only allowlisted capabilities are user-answerable; anything else raises.
[UC-6] the answer is durable: it lives in the per-vacuum record, NOT the stored adapter
       config, which is documented to flip-flop back at the next restart.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.adapters.registry import (
    clear_registry,
    register_adapter_config,
)

from tests._factories import VAC as _VAC

_CAP = "supports_cleaning_path"


def _declare(vacuum, value):
    """Register an adapter whose DERIVED answer is `value` (None = declares nothing)."""
    caps = {} if value is None else {_CAP: value}
    # source="code", not "config": a CONFIG-sourced adapter is hard-raised when it
    # declares no `room_profiles`, and this probe is about capabilities only.
    register_adapter_config(
        vacuum,
        {"adapter_id": "probe", "source": "code", "capabilities": caps},
    )


async def test_uc_1_nobody_knows_is_a_real_answer(manager):
    """[UC-1] None means "not established", and it is NOT False.

    A consumer that collapses the two denies the control to every brand nobody has
    asked — which is how a model-family guess came to speak for unexamined hardware.
    """
    clear_registry()
    _declare(_VAC, None)

    assert manager.resolve_vacuum_capability(
        vacuum_entity_id=_VAC, capability=_CAP
    ) is None


@pytest.mark.parametrize("derived", [True, False])
async def test_uc_2_a_derived_answer_is_used_when_the_user_is_silent(manager, derived):
    """[UC-2] A brand that can see the device still answers for it."""
    clear_registry()
    _declare(_VAC, derived)

    assert manager.resolve_vacuum_capability(
        vacuum_entity_id=_VAC, capability=_CAP
    ) is derived


@pytest.mark.parametrize(
    "derived,answer", [(False, True), (True, False), (None, True), (None, False)]
)
async def test_uc_3_the_user_wins(manager, derived, answer):
    """[UC-3] THE POINT OF THE CHANGE, in both directions.

    Overriding False->True is the headline — a guess denying a real capability — but
    True->False matters too: a user whose device publishes the control yet rejects the
    command can switch it off rather than live with a setting that does nothing.
    """
    clear_registry()
    _declare(_VAC, derived)

    manager.set_vacuum_capability(
        vacuum_entity_id=_VAC, capability=_CAP, supported=answer
    )

    assert manager.resolve_vacuum_capability(
        vacuum_entity_id=_VAC, capability=_CAP
    ) is answer


async def test_uc_4_clearing_hands_the_question_back(manager):
    """[UC-4] A wrong answer must never be a trap."""
    clear_registry()
    _declare(_VAC, False)
    manager.set_vacuum_capability(
        vacuum_entity_id=_VAC, capability=_CAP, supported=True
    )
    assert manager.resolve_vacuum_capability(
        vacuum_entity_id=_VAC, capability=_CAP
    ) is True

    result = manager.set_vacuum_capability(
        vacuum_entity_id=_VAC, capability=_CAP, supported=None
    )

    assert result["answered"] is False
    assert manager.resolve_vacuum_capability(
        vacuum_entity_id=_VAC, capability=_CAP
    ) is False, "clearing must fall back to what the brand derived, not to None"


async def test_uc_5_only_allowlisted_capabilities_are_user_answerable(manager):
    """[UC-5] The allowlist is the declaration-proving gate.

    A capability belongs there only when "we don't know" is the honest state. Without
    it this becomes a back door for overriding anything the integration detected, and
    a user could switch off a capability whose absence is a hardware fact.
    """
    clear_registry()
    _declare(_VAC, None)

    with pytest.raises(ValueError, match="not user-answerable"):
        manager.set_vacuum_capability(
            vacuum_entity_id=_VAC, capability="supports_mop_wash", supported=True
        )
    with pytest.raises(ValueError, match="not user-answerable"):
        manager.set_vacuum_capability(
            vacuum_entity_id=_VAC, capability="supports_path_control", supported=True
        )


async def test_uc_6_the_answer_is_stored_somewhere_durable(manager):
    """[UC-6] NOT the stored adapter config, which was the obvious home.

    `adapters/config_loader.py` documents that path as a flip-flop: a saved config wins
    until the next restart, when startup ordering hands the vacuum back to the code
    adapter. An answer that silently expires on reboot is worse than no answer, because
    the user believes they have set it. This lives in the per-vacuum record, beside
    `pause_timeout_minutes_default`, which survives.
    """
    clear_registry()
    _declare(_VAC, False)
    manager.set_vacuum_capability(
        vacuum_entity_id=_VAC, capability=_CAP, supported=True
    )

    record = manager.data["vacuums"][_VAC]
    assert record["user_capabilities"][_CAP] is True
    assert _CAP not in (manager.data.get("adapters") or {}).get(_VAC, {}), (
        "stored in the adapter config, which is documented to revert at the next restart"
    )
