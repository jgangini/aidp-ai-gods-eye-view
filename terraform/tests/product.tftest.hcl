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
  bucket_modes           = jsonencode({ landing = "new", bronze = "new", silver = "new", gold = "new", artifacts = "new" })
}
run "new_platform_owned" {
  command = plan
  assert {
    condition = (
      !issensitive(output.deploy_studio_resource_labels) &&
      toset(keys(output.deploy_studio_resource_labels)) == toset([
        "data.oci_objectstorage_namespace.product",
        "oci_core_vcn.product",
        "oci_core_internet_gateway.product",
        "oci_core_route_table.product",
        "oci_core_security_list.product",
        "oci_core_subnet.product",
        "oci_core_instance.product",
        "oci_identity_domains_group.readers",
        "oci_identity_domains_app.viewer",
        "oci_identity_dynamic_group.bootstrap",
        "oci_identity_policy.bootstrap",
        "oci_ai_data_platform_ai_data_platform.product[0]",
        "oci_identity_policy.aidp_service[0]",
        "time_sleep.aidp_iam_propagation[0]",
        "oci_objectstorage_bucket.product[\"landing\"]",
        "oci_objectstorage_bucket.product[\"bronze\"]",
        "oci_objectstorage_bucket.product[\"silver\"]",
        "oci_objectstorage_bucket.product[\"gold\"]",
        "oci_objectstorage_bucket.product[\"artifacts\"]",
      ]) &&
      alltrue([for label in values(output.deploy_studio_resource_labels) : length(label) > 0 && length(label) <= 80])
    )
    error_message = "Display labels must be available during PLAN, nonsensitive, and cover exactly the selected resource and data instances."
  }

  assert {
    condition     = oci_ai_data_platform_ai_data_platform.product[0].display_name == var.name
    error_message = "Omitting an explicit AIDP display name must preserve the infrastructure prefix contract."
  }
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
run "new_platform_display_name_is_separate" {
  command = plan
  variables {
    new_aidp_name = "aidp_gods_eye_view"
    name          = "existing-prefix"
    bucket_modes  = jsonencode({ landing = "existing", bronze = "existing", silver = "existing", gold = "existing", artifacts = "existing" })
  }
  assert {
    condition     = oci_ai_data_platform_ai_data_platform.product[0].display_name == "aidp_gods_eye_view" && output.default_workspace_name == "existing-prefix-workspace" && oci_core_instance.product.display_name == "existing-prefix"
    error_message = "The AIDP display name must not rename the viewer infrastructure or workspace."
  }
  assert {
    condition     = length(oci_objectstorage_bucket.product) == 0
    error_message = "Selecting existing must not create any buckets."
  }
}
run "existing_platform_external" {
  command = plan
  assert {
    condition = (
      !issensitive(output.deploy_studio_resource_labels) &&
      toset(keys(output.deploy_studio_resource_labels)) == toset([
        "data.oci_objectstorage_namespace.product",
        "oci_core_vcn.product",
        "oci_core_internet_gateway.product",
        "oci_core_route_table.product",
        "oci_core_security_list.product",
        "oci_core_subnet.product",
        "oci_core_instance.product",
        "oci_identity_domains_group.readers",
        "oci_identity_domains_app.viewer",
        "oci_identity_dynamic_group.bootstrap",
        "oci_identity_policy.bootstrap",
        "data.oci_ai_data_platform_ai_data_platform.existing[0]",
      ]) &&
      alltrue([for label in values(output.deploy_studio_resource_labels) : length(label) > 0 && length(label) <= 80])
    )
    error_message = "Display labels must be available during PLAN, nonsensitive, and cover exactly the selected resource and data instances."
  }

  variables {
    aidp_mode                      = "existing"
    existing_ai_data_platform_ocid = "ocid1.aidataplatform.oc1..external"
    existing_workspace_key         = "external-workspace"
    bucket_modes                   = jsonencode({ landing = "existing", bronze = "existing", silver = "existing", gold = "existing", artifacts = "existing" })
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
run "existing_artifacts_new_medallion" {
  command = plan
  variables {
    bucket_modes = jsonencode({ landing = "new", bronze = "new", silver = "new", gold = "new", artifacts = "existing" })
  }
  assert {
    condition     = toset(keys(oci_objectstorage_bucket.product)) == toset(["landing", "bronze", "silver", "gold"])
    error_message = "Reusing Artifacts must not suppress new Medallion buckets or claim the existing artifacts bucket."
  }
}
run "new_artifacts_existing_medallion" {
  command = plan
  variables {
    bucket_modes = jsonencode({ landing = "existing", bronze = "existing", silver = "existing", gold = "existing", artifacts = "new" })
  }
  assert {
    condition     = keys(oci_objectstorage_bucket.product) == ["artifacts"] && output.bucket_modes["landing"] == "existing"
    error_message = "Creating Artifacts must not claim the four existing Medallion buckets."
  }
}
run "mixed_individual_buckets" {
  command = plan
  assert {
    condition     = toset([for address in keys(output.deploy_studio_resource_labels) : address if startswith(address, "oci_objectstorage_bucket.")]) == toset(["oci_objectstorage_bucket.product[\"landing\"]", "oci_objectstorage_bucket.product[\"silver\"]", "oci_objectstorage_bucket.product[\"artifacts\"]"]) && output.deploy_studio_resource_labels["oci_objectstorage_bucket.product[\"landing\"]"] == "Landing bucket"
    error_message = "Plan resource labels must identify the selected infrastructure without exposing instance suffixes."
  }

  variables {
    bucket_modes = jsonencode({ landing = "new", bronze = "existing", silver = "new", gold = "existing", artifacts = "new" })
  }
  assert {
    condition     = toset(keys(oci_objectstorage_bucket.product)) == toset(["landing", "silver", "artifacts"])
    error_message = "Each bucket must retain its individual creation ownership and stable resource address."
  }
}
run "reject_partial_modes" {
  command = plan
  variables {
    bucket_modes = jsonencode({ artifacts = "new" })
  }
  expect_failures = [var.bucket_modes]
}
run "first_bootstrap_ip_origin" {
  command = apply
  assert {
    condition     = output.public_origin == "https://198.51.100.10" && contains(oci_identity_domains_app.viewer.redirect_uris, "https://198.51.100.10/api/auth/oci/callback")
    error_message = "OIDC callback and viewer origin must follow the allocated VM IP, without a user-supplied domain."
  }
}
