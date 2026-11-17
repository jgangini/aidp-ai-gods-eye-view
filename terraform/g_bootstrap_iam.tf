resource "oci_identity_dynamic_group" "bootstrap" {
  provider       = oci.home
  compartment_id = var.tenancy_ocid
  name           = "${var.name}-bootstrap"
  description    = "Exact product VM operator delivery"
  matching_rule  = "ALL {instance.id = '${oci_core_instance.product.id}'}"
}
resource "oci_identity_policy" "bootstrap" {
  provider       = oci.home
  compartment_id = var.compartment_ocid
  name           = "${var.name}-bootstrap"
  description    = "Read immutable bundle and consume one exact encrypted operator object"
  statements = [
    "Allow dynamic-group ${oci_identity_dynamic_group.bootstrap.name} to read objects in compartment id ${var.compartment_ocid} where all {target.bucket.name='${var.artifacts_bucket_name}', target.object.name='${var.vm_bundle_object}'}",
    "Allow dynamic-group ${oci_identity_dynamic_group.bootstrap.name} to read objects in compartment id ${var.compartment_ocid} where all {target.bucket.name='${var.artifacts_bucket_name}', any {target.object.name='releases/${var.source_commit_sha}/gods-eye-view-api-image-amd64.tar.gz', target.object.name='releases/${var.source_commit_sha}/gods-eye-view-image-amd64.tar.gz', target.object.name='releases/${var.source_commit_sha}/gods-eye-view-gateway-image-amd64.tar.gz'}}",
    "Allow dynamic-group ${oci_identity_dynamic_group.bootstrap.name} to manage objects in compartment id ${var.compartment_ocid} where all {target.bucket.name='${var.artifacts_bucket_name}', target.object.name='.bootstrap/gods-eye-view/${var.deployment_id}/operator.json', any {request.permission='OBJECT_READ', request.permission='OBJECT_DELETE'}}"
  ]
}
