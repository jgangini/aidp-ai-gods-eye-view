# Service policy preserved from frozen source; existing platforms remain externally managed.
resource "oci_identity_policy" "aidp_service" {
  count          = var.aidp_mode == "new" ? 1 : 0
  provider       = oci.home
  compartment_id = var.tenancy_ocid
  name           = "${var.name}-aidp-service"
  description    = "Minimum AIDP Workbench service access for the lab compartment"
  statements = [
    "Allow any-user to {AUTHENTICATION_INSPECT, DOMAIN_INSPECT, DOMAIN_READ, DYNAMIC_GROUP_INSPECT, GROUP_INSPECT, GROUP_MEMBERSHIP_INSPECT, USER_INSPECT, USER_READ} in tenancy where all {request.principal.type='aidataplatform'}",
    "Allow any-user to manage log-groups in compartment id ${var.compartment_ocid} where all {request.principal.type='aidataplatform'}",
    "Allow any-user to read log-content in compartment id ${var.compartment_ocid} where all {request.principal.type='aidataplatform'}",
    "Allow any-user to use metrics in compartment id ${var.compartment_ocid} where all {request.principal.type='aidataplatform', target.metrics.namespace='oracle_aidataplatform'}",
    "Allow any-user to manage buckets in compartment id ${var.compartment_ocid} where all {request.principal.type='aidataplatform', any {request.permission='BUCKET_CREATE', request.permission='BUCKET_INSPECT', request.permission='BUCKET_READ', request.permission='BUCKET_UPDATE'}}",
    "Allow any-user to {TAG_NAMESPACE_USE} in tenancy where all {request.principal.type='aidataplatform'}",
    "Allow any-user to manage buckets in compartment id ${var.compartment_ocid} where all {request.principal.id=target.resource.tag.orcl-aidp.governingAidpId, any {request.permission='BUCKET_DELETE', request.permission='PAR_MANAGE', request.permission='RETENTION_RULE_LOCK', request.permission='RETENTION_RULE_MANAGE'}}",
    "Allow any-user to read objectstorage-namespaces in compartment id ${var.compartment_ocid} where all {request.principal.type='aidataplatform', request.permission='OBJECTSTORAGE_NAMESPACE_READ'}",
    "Allow any-user to manage objects in compartment id ${var.compartment_ocid} where all {request.principal.id=target.bucket.system-tag.orcl-aidp.governingAidpId}",
    "Allow any-user to use generative-ai-family in compartment id ${var.compartment_ocid} where all {request.principal.type='aidataplatform'}"
  ]
}

