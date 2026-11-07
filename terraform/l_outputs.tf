output "ai_data_platform_id" { value = local.platform_id }
output "existing_workspace_key" { value = var.existing_workspace_key }
output "default_workspace_name" { value = "${var.name}-workspace" }
output "objectstorage_namespace" { value = data.oci_objectstorage_namespace.product.namespace }
output "medallion_bucket_names" { value = jsondecode(var.medallion_bucket_names) }
output "bucket_modes" { value = local.bucket_modes }
output "artifacts_bucket_name" { value = var.artifacts_bucket_name }
output "compartment_ocid" { value = var.compartment_ocid }
output "instance_id" { value = oci_core_instance.product.id }
output "admin_user_ocid" { value = var.admin_user_ocid }
output "identity_domain_id" { value = var.identity_domain_id }
output "identity_domain_url" { value = var.identity_domain_url }
output "gods_eye_view_group_id" { value = oci_identity_domains_group.readers.id }
output "viewer_oidc_app_name" { value = oci_identity_domains_app.viewer.name }
output "public_origin" { value = local.public_origin }
output "agent_model_id" { value = var.agent_model_id }

output "deploy_studio_resource_labels" {
  description = "Plan-known display labels keyed by exact Terraform instance address; execution and ordering come from OCI Resource Manager."
  value = merge(
    {
      "data.oci_objectstorage_namespace.product" = "Object Storage namespace discovery"
      "oci_core_vcn.product"                     = "Virtual cloud network"
      "oci_core_internet_gateway.product"        = "Internet gateway"
      "oci_core_route_table.product"             = "Public network routes"
      "oci_core_security_list.product"           = "Viewer network security"
      "oci_core_subnet.product"                  = "Viewer subnet"
      "oci_core_instance.product"                = "God's Eye View application VM"
      "oci_identity_domains_group.readers"       = "Viewer reader group"
      "oci_identity_domains_app.viewer"          = "Viewer OCI sign-in application"
      "oci_identity_dynamic_group.bootstrap"     = "Viewer instance identity"
      "oci_identity_policy.bootstrap"            = "Viewer bootstrap permissions"
    },
    { for index, instance in oci_ai_data_platform_ai_data_platform.product : "oci_ai_data_platform_ai_data_platform.product[${index}]" => "AI Data Platform" },
    { for index, instance in data.oci_ai_data_platform_ai_data_platform.existing : "data.oci_ai_data_platform_ai_data_platform.existing[${index}]" => "Existing AI Data Platform" },
    { for index, instance in oci_identity_policy.aidp_service : "oci_identity_policy.aidp_service[${index}]" => "AIDP service permissions" },
    { for index, instance in time_sleep.aidp_iam_propagation : "time_sleep.aidp_iam_propagation[${index}]" => "IAM permission propagation" },
    { for key, instance in oci_objectstorage_bucket.product : "oci_objectstorage_bucket.product[${jsonencode(key)}]" => "${title(key)} bucket" }
  )
}
