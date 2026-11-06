variable "region" { type = string }
variable "home_region" { type = string }
variable "tenancy_ocid" { type = string }
variable "compartment_ocid" { type = string }
variable "admin_user_ocid" { type = string }
variable "identity_domain_id" { type = string }
variable "identity_domain_url" { type = string }
variable "operator_user_ocid" { type = string }
variable "operator_fingerprint" { type = string }
variable "vm_bundle_object" {
  type = string
  validation {
    condition     = can(regex("^releases/[a-zA-Z0-9/_-]+[.]zip$", var.vm_bundle_object))
    error_message = "Use a release-scoped immutable bundle object path."
  }
}
variable "vm_bundle_sha256" {
  type = string
  validation {
    condition     = can(regex("^[0-9a-f]{64}$", var.vm_bundle_sha256))
    error_message = "Pin the SHA-256 of the immutable VM bundle."
  }
}
variable "deployment_id" {
  type = string
  validation {
    condition     = can(regex("^[A-Za-z0-9_-]{1,128}$", var.deployment_id))
    error_message = "Invalid deployment identity."
  }
}
variable "aidp_mode" {
  type = string
  validation {
    condition     = contains(["new", "existing"], var.aidp_mode)
    error_message = "Select new or existing AIDP."
  }
}
variable "existing_ai_data_platform_ocid" {
  type    = string
  default = ""
}
variable "existing_workspace_key" {
  type    = string
  default = ""
}
variable "name" {
  type    = string
  default = "aidp-gods-eye-view"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,40}$", var.name))
    error_message = "Use a stable resource prefix."
  }
}
variable "new_aidp_name" {
  type    = string
  default = null
  validation {
    condition     = var.new_aidp_name == null || can(regex("^[A-Za-z0-9][A-Za-z0-9._ -]{0,254}$", var.new_aidp_name))
    error_message = "Use an AIDP display name of 1 to 255 letters, digits, spaces, dots, underscores or hyphens."
  }
}
variable "medallion_bucket_names" {
  type = string
  validation {
    condition     = toset(keys(jsondecode(var.medallion_bucket_names))) == toset(["landing", "bronze", "silver", "gold"]) && length(toset(values(jsondecode(var.medallion_bucket_names)))) == 4
    error_message = "Select four distinct medallion buckets."
  }
}
variable "artifacts_bucket_name" { type = string }
variable "create_buckets" {
  type    = bool
  default = true
}
variable "availability_domain" { type = string }
variable "image_ocid" { type = string }
variable "vm_shape" {
  type    = string
  default = "VM.Standard.E5.Flex"
}
variable "source_commit_sha" {
  type = string
  validation {
    condition     = can(regex("^[0-9a-f]{40}$", var.source_commit_sha))
    error_message = "Pin a full source commit."
  }
}
variable "agent_model_id" { type = string }
