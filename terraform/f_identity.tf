resource "oci_identity_domains_group" "readers" {
  idcs_endpoint = var.identity_domain_url
  schemas       = ["urn:ietf:params:scim:schemas:core:2.0:Group"]
  display_name  = "${var.name}-readers"
  external_id   = "${var.deployment_id}:gods_eye_view"
  lifecycle { ignore_changes = [schemas] }
}
resource "oci_identity_domains_app" "viewer" {
  idcs_endpoint = var.identity_domain_url
  schemas       = ["urn:ietf:params:scim:schemas:oracle:idcs:App"]
  display_name  = "God's Eye View ${var.name}"
  name          = replace("${var.name}_viewer", "-", "_")
  based_on_template { value = "CustomBrowserMobileTemplateId" }
  active          = true
  is_oauth_client = true
  client_type     = "public"
  allowed_grants  = ["authorization_code"]
  redirect_uris   = ["${var.public_origin}/api/auth/oci/callback"]
  lifecycle { ignore_changes = [schemas] }
}
