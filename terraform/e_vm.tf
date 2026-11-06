resource "oci_core_instance" "product" {
  compartment_id      = var.compartment_ocid
  availability_domain = var.availability_domain
  display_name        = var.name
  shape               = var.vm_shape
  shape_config {
    ocpus         = 2
    memory_in_gbs = 16
  }
  create_vnic_details {
    subnet_id        = oci_core_subnet.product.id
    assign_public_ip = true
  }
  source_details {
    source_type = "image"
    source_id   = var.image_ocid
  }
  agent_config {
    plugins_config {
      name          = "Compute Instance Run Command"
      desired_state = "ENABLED"
    }
  }
  metadata = {
    user_data = base64encode(templatefile("${path.module}/templatefile/user_data.sh", {
      namespace            = data.oci_objectstorage_namespace.product.namespace
      bucket               = var.artifacts_bucket_name
      bundle_object        = var.vm_bundle_object
      bundle_sha256        = var.vm_bundle_sha256
      deployment_id        = var.deployment_id
      operator_user_ocid   = var.operator_user_ocid
      operator_fingerprint = var.operator_fingerprint
    }))
  }
  lifecycle {
    prevent_destroy = true
    ignore_changes  = [source_details[0].source_id, metadata["user_data"]]
  }
}
