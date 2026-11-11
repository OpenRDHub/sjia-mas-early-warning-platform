from rareguard.ehr.provider import BaseEHRProvider, PatientNotFound


READ_METHODS = {
    "get_patient",
    "get_encounters",
    "get_observations",
    "get_medications",
    "get_allergies",
}

FORBIDDEN_PREFIXES = ("write", "update", "set", "delete", "insert", "save", "create", "patch")


def test_interface_exposes_only_the_five_read_methods():
    public = {m for m in dir(BaseEHRProvider) if not m.startswith("_")}
    assert public == READ_METHODS


def test_interface_has_no_write_capable_method_names():
    public = {m for m in dir(BaseEHRProvider) if not m.startswith("_")}
    assert not [m for m in public if m.lower().startswith(FORBIDDEN_PREFIXES)]


def test_mock_provider_returns_seeded_patient():
    from rareguard.ehr.mock_provider import MockEHRProvider

    provider = MockEHRProvider()
    patient = provider.get_patient("P001")
    assert patient["name"]
    assert patient["id"] == "P001"


def test_mock_provider_returns_allergies_and_medications():
    from rareguard.ehr.mock_provider import MockEHRProvider

    provider = MockEHRProvider()
    assert provider.get_allergies("P001")
    assert provider.get_medications("P001")
    assert provider.get_observations("P001")
    assert provider.get_encounters("P001")


def test_mock_provider_raises_for_unknown_patient():
    from rareguard.ehr.mock_provider import MockEHRProvider

    import pytest

    with pytest.raises(PatientNotFound):
        MockEHRProvider().get_patient("NOPE")
