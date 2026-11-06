"""Resolve first-boot inputs from the authorized OCI context and pinned source."""
import hashlib
from pathlib import Path
import sys
from oci.pagination import list_call_get_all_results


def vm_inputs(context, config, compute, identity):
    values = context.get("inputs", {})
    scope = context.get("compartment", {}).get("id") or config["tenancy"]
    shape = values.get("vm_shape", "VM.Standard.E5.Flex")
    image_id = values.get("image_ocid")
    if not image_id:
        images = list_call_get_all_results(compute.list_images, scope, operating_system="Oracle Linux", operating_system_version="9",
            shape=shape, lifecycle_state="AVAILABLE", sort_by="TIMECREATED", sort_order="DESC", limit=10).data
        public = [item for item in images if getattr(item, "compartment_id", None) is None]
        if not public:
            raise ValueError("No compatible Oracle Linux 9 platform image is available")
        image_id = public[0].id
    image = compute.get_image(image_id).data
    if image.id != image_id or image.operating_system != "Oracle Linux" or str(image.operating_system_version).split(".")[0] != "9" or image.lifecycle_state != "AVAILABLE":
        raise ValueError("The VM requires an available Oracle Linux 9 image")
    domains = sorted(item.name for item in list_call_get_all_results(identity.list_availability_domains, config["tenancy"]).data)
    preferred = values.get("availability_domain")
    if preferred and preferred not in domains:
        raise ValueError("The selected availability domain is unavailable")
    domain = next((name for name in ([preferred] if preferred else domains) if any(
        item.shape == shape for item in list_call_get_all_results(compute.list_shapes, scope, availability_domain=name, image_id=image_id).data)), None)
    if domain is None:
        raise ValueError("The selected VM shape and image are incompatible in this availability domain")
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "scripts/deployment"))
    from build_vm_bundle import build
    digest = hashlib.sha256(build(root)).hexdigest()
    return {"image_ocid": image_id, "availability_domain": domain,
        "vm_bundle_sha256": digest, "vm_bundle_object": f"releases/{values['source_commit_sha']}/vm-bootstrap-{digest}.zip"}
