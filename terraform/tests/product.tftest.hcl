mock_provider "oci" {
  mock_resource "oci_core_instance" {
    defaults = { public_ip = "198.51.100.10" }
  }
  mock_data "oci_ai_data_platform_ai_data_platform" {
    defaults = { state = "ACTIVE" }
  }
}
mock_provider "oci" { alias = "home" }
mock_provider "time" {}
variables {
  home_region            = "us-ashburn-1"
  region                 = "us-chicago-1"
  tenancy_ocid           = "ocid1.tenancy.oc1..test"
  compartment_ocid       = "ocid1.compartment.oc1..test"
  admin_user_ocid        = "ocid1.user.oc1..selected"
  operator_user_ocid     = "ocid1.user.oc1..operator"
  operator_fingerprint   = "0123456789abcdef0123456789abcdef"
  identity_domain_id     = "ocid1.domain.oc1..test"
  identity_domain_url    = "https://idcs-test.identity.oraclecloud.com"
  deployment_id          = "test-deployment"
  availability_domain    = "test:US-CHICAGO-1-AD-1"
  image_ocid             = "ocid1.image.oc1..test"
  aidp_mode              = "new"
  agent_model_id         = "test-model"
  source_commit_sha      = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  vm_bundle_object       = "releases/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/vm.zip"
  vm_bundle_sha256       = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  artifacts_bucket_name  = "test-artifacts"
  medallion_bucket_names = jsonencode({ landing = "test-landing", bronze = "test-bronze", silver = "test-silver", gold = "test-gold" })
}
run "new_platform_owned" {
  command = plan
  assert {
    condition     = length(oci_ai_data_platform_ai_data_platform.product) == 1 && length(data.oci_ai_data_platform_ai_data_platform.existing) == 0
    error_message = "New platform must be owned exclusively by this stack."
  }
  assert {
    condition     = length(oci_objectstorage_bucket.product) == 5
    error_message = "Five isolated buckets required."
  }
  assert {
    condition     = tolist(oci_core_security_list.product.ingress_security_rules)[0].tcp_options[0].min == 443
    error_message = "Only gateway TLS may be public."
  }
}
run "existing_platform_external" {
  command = plan
  variables {
    aidp_mode                      = "existing"
    existing_ai_data_platform_ocid = "ocid1.aidataplatform.oc1..external"
    existing_workspace_key         = "external-workspace"
    create_buckets                 = false
  }
  assert {
    condition     = length(oci_ai_data_platform_ai_data_platform.product) == 0 && length(oci_objectstorage_bucket.product) == 0
    error_message = "External AIDP and buckets must never become managed resources."
  }
  assert {
    condition     = output.ai_data_platform_id == "ocid1.aidataplatform.oc1..external"
    error_message = "Do not replace or adopt the selected external identity."
  }
}
run "first_bootstrap_ip_origin" {
  command = apply
  assert {
    condition     = output.public_origin == "https://198.51.100.10" && contains(oci_identity_domains_app.viewer.redirect_uris, "https://198.51.100.10/api/auth/oci/callback")
    error_message = "OIDC callback and viewer origin must follow the allocated VM IP, without a user-supplied domain."
  }
}
