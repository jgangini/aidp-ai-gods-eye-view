"""Independent bucket choices preserve exact bindings without adopting external buckets."""
import copy
from itertools import combinations, product
import json
from pathlib import Path
import sys
from types import SimpleNamespace

from oci.exceptions import ServiceError
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "terraform/hooks"))
import preflight


LAYERS = ("landing", "bronze", "silver", "gold", "artifacts")
COMPARTMENT = "ocid1.compartment.oc1..selected"
TENANCY = "ocid1.tenancy.oc1..operator"
CONFIG = {"tenancy": TENANCY, "region": "us-chicago-1"}
MIXES = list(product(("new", "existing"), repeat=len(LAYERS)))


def mode_field(layer):
    return "artifacts_mode" if layer == "artifacts" else layer + "_bucket_mode"


def name_field(layer, mode):
    if layer == "artifacts":
        return "artifacts_bucket_name" if mode == "new" else "artifacts_existing_bucket_name"
    return layer + ("_new_bucket_name" if mode == "new" else "_existing_bucket_name")


def selections(modes):
    values = {"unrelated_binding": "preserve-this-value"}
    for layer, mode in zip(LAYERS, modes):
        values[mode_field(layer)] = mode
        values[name_field(layer, mode)] = "selected-" + layer
    return values


def runner_context(inputs, resolved=False):
    context = {"inputs": inputs, "region": CONFIG["region"]}
    if resolved:
        context.update(compartment={"id": COMPARTMENT, "name": "selected"},
            terraform_outputs={"compartment_ocid": COMPARTMENT})
    else:
        context.update(compartment=COMPARTMENT, compartment_mode="existing")
    return context


class ReadOnlyStorage:
    """Only the two authorized GET operations exist; every unexpected bucket read fails."""
    def __init__(self, allowed):
        self.allowed = set(allowed)
        self.calls = []
        self.error = None
        self.namespace_error = None
        self.returned_name = None
        self.returned_compartment = COMPARTMENT

    def get_namespace(self, *, compartment_id):
        assert compartment_id == TENANCY
        self.calls.append(("namespace", compartment_id))
        if self.namespace_error:
            raise self.namespace_error
        return SimpleNamespace(data="selected_namespace")

    def get_bucket(self, namespace_name, bucket_name):
        assert namespace_name == "selected_namespace"
        assert bucket_name in self.allowed, "A new or unselected bucket must not be read"
        self.calls.append(("bucket", namespace_name, bucket_name))
        if self.error:
            raise self.error
        return SimpleNamespace(data=SimpleNamespace(name=self.returned_name or bucket_name,
            compartment_id=self.returned_compartment))


@pytest.mark.parametrize("modes", MIXES, ids=lambda modes: "-".join(modes))
def test_all_32_bucket_mode_combinations_normalize_exact_names_and_modes(modes):
    assert tuple(preflight.BUCKET_LAYERS) == LAYERS
    inputs = selections(modes)
    original = copy.deepcopy(inputs)
    actual = preflight.bucket_inputs(inputs)
    assert inputs == original
    assert actual["unrelated_binding"] == inputs["unrelated_binding"]
    for key, value in inputs.items():
        assert actual[key] == value
    assert isinstance(actual["medallion_bucket_names"], str)
    assert json.loads(actual["medallion_bucket_names"]) == {layer: "selected-" + layer for layer in LAYERS[:-1]}
    assert isinstance(actual["bucket_modes"], str)
    assert json.loads(actual["bucket_modes"]) == dict(zip(LAYERS, modes))
    assert actual["artifacts_bucket_name"] == "selected-artifacts"
    assert preflight.bucket_inputs(actual) == actual


@pytest.mark.parametrize("resolved", [False, True], ids=["preflight-compartment", "postapply-compartment"])
@pytest.mark.parametrize("modes", MIXES, ids=lambda modes: "-".join(modes))
def test_existing_bucket_checks_only_read_selected_existing_buckets(modes, resolved):
    inputs = selections(modes)
    original = copy.deepcopy(inputs)
    existing = ["selected-" + layer for layer, mode in zip(LAYERS, modes) if mode == "existing"]
    storage = ReadOnlyStorage(existing)
    preflight.verify_existing_buckets(runner_context(inputs, resolved), CONFIG, storage)
    assert inputs == original
    if existing:
        assert storage.calls[0] == ("namespace", TENANCY)
        assert sorted(storage.calls[1:]) == sorted(("bucket", "selected_namespace", bucket) for bucket in existing)
    else:
        assert not storage.calls


@pytest.mark.parametrize("layer", LAYERS)
def test_every_layer_requires_an_explicit_mode_without_legacy_fallback(layer):
    inputs = selections(("new",) * len(LAYERS))
    del inputs[mode_field(layer)]
    storage = ReadOnlyStorage(())
    with pytest.raises(ValueError):
        preflight.bucket_inputs(inputs)
    with pytest.raises(ValueError):
        preflight.verify_existing_buckets(runner_context(inputs), CONFIG, storage)
    assert not storage.calls


@pytest.mark.parametrize("invalid", [None, True, "", "NEW", "false"])
@pytest.mark.parametrize("layer", LAYERS)
def test_every_layer_rejects_invalid_modes(layer, invalid):
    inputs = selections(("new",) * len(LAYERS))
    inputs[mode_field(layer)] = invalid
    with pytest.raises(ValueError):
        preflight.bucket_inputs(inputs)


@pytest.mark.parametrize("legacy", [True, False, "true", "false", None])
def test_global_create_buckets_is_rejected_even_with_complete_individual_choices(legacy):
    inputs = {**selections(("new",) * len(LAYERS)), "create_buckets": legacy}
    storage = ReadOnlyStorage(())
    with pytest.raises(ValueError):
        preflight.bucket_inputs(inputs)
    with pytest.raises(ValueError):
        preflight.verify_existing_buckets(runner_context(inputs), CONFIG, storage)
    assert not storage.calls


def test_old_canonical_names_alone_do_not_supply_individual_choices():
    with pytest.raises(ValueError):
        preflight.bucket_inputs({"artifacts_bucket_name": "old-artifacts",
            "medallion_bucket_names": json.dumps({layer: "old-" + layer for layer in LAYERS[:-1]})})


@pytest.mark.parametrize("mode", ["new", "existing"])
@pytest.mark.parametrize("layer", LAYERS)
def test_selected_bucket_name_is_required(layer, mode):
    inputs = selections((mode,) * len(LAYERS))
    del inputs[name_field(layer, mode)]
    with pytest.raises(ValueError):
        preflight.bucket_inputs(inputs)


@pytest.mark.parametrize("invalid", [None, True, 123, "", "bad/name", "bad name", "bad\nname", "a" * 129])
@pytest.mark.parametrize("mode", ["new", "existing"])
@pytest.mark.parametrize("layer", LAYERS)
def test_selected_bucket_names_are_validated_in_both_modes(layer, invalid, mode):
    inputs = selections((mode,) * len(LAYERS))
    inputs[name_field(layer, mode)] = invalid
    with pytest.raises(ValueError):
        preflight.bucket_inputs(inputs)


@pytest.mark.parametrize("first,second", list(combinations(LAYERS, 2)))
def test_all_five_selected_bucket_names_must_be_distinct(first, second):
    inputs = selections(("new",) * len(LAYERS))
    inputs[name_field(second, "new")] = inputs[name_field(first, "new")]
    with pytest.raises(ValueError):
        preflight.bucket_inputs(inputs)


def test_inactive_selector_cannot_replace_the_name_chosen_by_the_mode():
    inputs = selections(("existing",) * len(LAYERS))
    for layer in LAYERS:
        inputs[name_field(layer, "new")] = "inactive-" + layer
    actual = preflight.bucket_inputs(inputs)
    assert actual["artifacts_bucket_name"] == "selected-artifacts"
    assert json.loads(actual["medallion_bucket_names"]) == {layer: "selected-" + layer for layer in LAYERS[:-1]}


@pytest.mark.parametrize("returned", ["name", "compartment"])
def test_existing_bucket_must_match_exact_name_and_compartment(returned):
    storage = ReadOnlyStorage({"selected-artifacts"})
    if returned == "name":
        storage.returned_name = "other-bucket"
    else:
        storage.returned_compartment = "ocid1.compartment.oc1..other"
    inputs = selections(("new", "new", "new", "new", "existing"))
    with pytest.raises(ValueError):
        preflight.verify_existing_buckets(runner_context(inputs), CONFIG, storage)


@pytest.mark.parametrize("failure", ["namespace", "bucket"])
def test_absent_or_cross_region_buckets_fail_with_a_bounded_error(failure):
    storage = ReadOnlyStorage({"selected-artifacts"})
    provider_message = "PRIVATE_PROVIDER_RESPONSE_DO_NOT_FORWARD"
    error = ServiceError(404, "BucketNotFound", {}, provider_message)
    if failure == "namespace":
        storage.namespace_error = error
    else:
        storage.error = error
    inputs = selections(("new", "new", "new", "new", "existing"))
    with pytest.raises(ValueError) as caught:
        preflight.verify_existing_buckets(runner_context(inputs), CONFIG, storage)
    assert provider_message not in str(caught.value)
    assert len(str(caught.value)) < 512


@pytest.mark.parametrize("layer", LAYERS)
def test_existing_bucket_with_new_compartment_is_rejected_before_any_request(layer):
    modes = tuple("existing" if item == layer else "new" for item in LAYERS)
    context = {"inputs": selections(modes), "compartment": "new-compartment", "compartment_mode": "new"}
    storage = ReadOnlyStorage({"selected-" + layer})
    with pytest.raises(ValueError):
        preflight.verify_existing_buckets(context, CONFIG, storage)
    assert not storage.calls


def test_all_new_buckets_need_no_storage_requests_even_with_a_new_compartment():
    context = {"inputs": selections(("new",) * len(LAYERS)),
        "compartment": "new-compartment", "compartment_mode": "new"}
    storage = ReadOnlyStorage(())
    preflight.verify_existing_buckets(context, CONFIG, storage)
    assert not storage.calls
