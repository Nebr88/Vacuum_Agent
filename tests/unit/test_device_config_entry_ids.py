"""Which config entries own a device — across the HA cores we support.

ISSUE #69. HA 2026.8 moved the answer from ``DeviceEntry.config_entries`` (a field) to
``DeviceEntry.config_entry_id`` (a field) plus a deprecated ``config_entries`` property
that reports its caller and is removed in 2027.10. `hacs.json` declares a 2025.6.0
floor, where ``config_entry_id`` does not exist on the class at all — so the one-line
swap the deprecation warning asks for is an AttributeError on every core below 2026.8.

These pin the only form that is correct on both sides. [DCE-5] is the one that notices
if the REAL class moves again; the rest pin the branches against hand-built shapes,
because the installed core can only ever present one of them.
"""
import pytest

from custom_components.eufy_vacuum.entity_helpers import device_config_entry_ids


class _OldShape:
    """HA <= 2026.7: ``config_entries`` is the field; no ``config_entry_id`` exists."""

    def __init__(self, entries):
        self.config_entries = set(entries)


class _NewShape:
    """HA >= 2026.8: ``config_entry_id`` is the field; ``config_entries`` DEPRECATES.

    The property RECORDS rather than raising. A raising stub would prove nothing here:
    ``dreame_coordinator``, one of the two callers, wraps its body in a blanket
    ``except Exception``, so a raise there is swallowed and the test passes whether or
    not the read happened. Recording the call is the form that bites in both seams.
    """

    def __init__(self, entry_id, deprecated_value=None):
        self.config_entry_id = entry_id
        self._deprecated_value = deprecated_value or {entry_id}
        self.deprecated_reads = 0

    @property
    def config_entries(self):
        self.deprecated_reads += 1
        return set(self._deprecated_value)


def test_dce1_old_core_answers_from_config_entries():
    """[DCE-1] Below 2026.8 the only answer is the field; the fallback must take it.

    ABLATION: delete the final ``config_entries`` branch and this goes red — which is
    exactly the install the naive fix would have broken.
    """
    assert device_config_entry_ids(_OldShape({"abc", "def"})) == {"abc", "def"}


def test_dce2_new_core_uses_the_new_name_and_never_touches_the_old_one():
    """[DCE-2] On 2026.8+ the deprecated property must not be read AT ALL.

    Returning the right value is not enough: reading ``config_entries`` to get it is
    the whole defect #69 reported. The count is the assertion.

    ABLATION: reorder the helper to try ``config_entries`` first and the count is 1.
    """
    dev = _NewShape("entry_a")
    assert device_config_entry_ids(dev) == {"entry_a"}
    assert dev.deprecated_reads == 0, (
        "the deprecated property was read; on a real core that emits the warning "
        "this fix was written to remove"
    )


def test_dce3_a_composite_device_keeps_every_split():
    """[DCE-3] A pre-migration composite spans entries; the new name names only one.

    Preferring ``config_entry_id`` here would silently narrow a multi-entry device to a
    single entry — a wrong answer that looks like a working one. The deprecation report
    is the correct price on this shape.

    ABLATION: drop the ``is_composite_device`` branch and this returns {"split_1"}.
    """
    dev = _NewShape("split_1", deprecated_value={"split_1", "split_2"})
    dev.is_composite_device = True
    assert device_config_entry_ids(dev) == {"split_1", "split_2"}
    assert dev.deprecated_reads == 1, "the composite answer comes FROM the old name"


@pytest.mark.parametrize(
    "device",
    [object(), _OldShape(set()), _NewShape("")],
    ids=["neither-attribute", "empty-set", "empty-id"],
)
def test_dce4_an_unanswerable_device_is_empty_not_an_exception(device):
    """[DCE-4] Callers iterate the result inside registry walks; empty, never a raise.

    ABLATION: change either ``getattr`` default to raise and the first case goes red.
    """
    assert device_config_entry_ids(device) == set()


def test_dce5_the_real_device_entry_emits_no_deprecation_report(hass):
    """[DCE-5] The one case built from the REAL class — and the only one that can
    notice HA renaming the field again.

    An earlier version of this test asserted the returned id and called that a rename
    guard. It was not one: ABLATING the new attribute name to a misspelling left it
    GREEN, because the helper then falls through to ``config_entries``, which on this
    core returns the very same id. The assertion could not distinguish the fixed code
    from the bug it was written to catch.

    What a rename actually changes is not the ANSWER, it is WHICH DOOR we go through —
    so that is what to assert. The deprecated property calls
    ``_report_deprecated_config_entries_property`` (`device_registry.py` L436 at
    2026.10.1); that call is the user-visible symptom #69 reported. Spying on it tests
    the real class with no hand-built shape in the way.

    ABLATION: misspell ``config_entry_id`` in the helper and this goes red, where the
    old form stayed green.
    """
    from homeassistant.helpers import device_registry as dr
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(domain="roborock", entry_id="dce5_entry")
    entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("roborock", "dce5_duid")},
    )

    reports = []
    original = dr._report_deprecated_config_entries_property
    dr._report_deprecated_config_entries_property = (
        lambda *a, **k: reports.append(a) or original(*a, **k)
    )
    try:
        assert device_config_entry_ids(device) == {"dce5_entry"}
    finally:
        dr._report_deprecated_config_entries_property = original

    assert reports == [], (
        "the helper reached the answer through the DEPRECATED property; on a real "
        f"install that is the warning ISSUE #69 reported — reports: {reports}"
    )
