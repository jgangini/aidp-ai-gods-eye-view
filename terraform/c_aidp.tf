locals {
  platform_id  = var.aidp_mode == "new" ? oci_ai_data_platform_ai_data_platform.product[0].id : var.existing_ai_data_platform_ocid
  buckets      = merge(jsondecode(var.medallion_bucket_names), { artifacts = var.artifacts_bucket_name })
  bucket_modes = jsondecode(var.bucket_modes)
}
resource "oci_ai_data_platform_ai_data_platform" "product" {
  depends_on             = [time_sleep.aidp_iam_propagation]
  count                  = var.aidp_mode == "new" ? 1 : 0
  compartment_id         = var.compartment_ocid
  display_name           = coalesce(var.new_aidp_name, var.name)
  default_workspace_name = "${var.name}-workspace"
  ai_data_platform_type  = "STRUCTURED"
  freeform_tags          = { managed-by = "deploy-studio", product = "gods_eye_view" }
  lifecycle { prevent_destroy = true }
  timeouts { create = "120m" }
}
data "oci_ai_data_platform_ai_data_platform" "existing" {
  count               = var.aidp_mode == "existing" ? 1 : 0
  ai_data_platform_id = var.existing_ai_data_platform_ocid
  lifecycle {
    postcondition {
      condition     = self.state == "ACTIVE"
      error_message = "Existing platform must be active."
    }
  }
}
data "oci_objectstorage_namespace" "product" { compartment_id = var.compartment_ocid }
resource "oci_objectstorage_bucket" "product" {
  for_each       = { for layer, name in local.buckets : layer => name if local.bucket_modes[layer] == "new" }
  compartment_id = var.compartment_ocid
  namespace      = data.oci_objectstorage_namespace.product.namespace
  name           = each.value
  access_type    = "NoPublicAccess"
  versioning     = "Enabled"
  lifecycle { prevent_destroy = true }
}
check "external_workspace" {
  assert {
    condition     = var.aidp_mode != "existing" || (var.existing_workspace_key != "" && var.existing_ai_data_platform_ocid != "")
    error_message = "Existing AIDP requires exact platform and workspace IDs."
  }
}
check "bucket_isolation" {
  assert {
    condition     = length(toset(values(local.buckets))) == 5
    error_message = "Artifacts must be distinct from all medallion buckets."
  }
}
