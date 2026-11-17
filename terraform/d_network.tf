resource "oci_core_vcn" "product" {
  compartment_id = var.compartment_ocid
  cidr_block     = "10.86.0.0/24"
  display_name   = var.name
}
resource "oci_core_internet_gateway" "product" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.product.id
  enabled        = true
}
resource "oci_core_route_table" "product" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.product.id
  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_internet_gateway.product.id
  }
}
resource "oci_core_security_list" "product" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.product.id
  ingress_security_rules {
    protocol = "6"
    source   = "0.0.0.0/0"
    tcp_options {
      min = 443
      max = 443
    }
  }
  egress_security_rules {
    protocol    = "6"
    destination = "0.0.0.0/0"
    tcp_options {
      min = 443
      max = 443
    }
  }
  egress_security_rules {
    protocol    = "6"
    destination = "0.0.0.0/0"
    tcp_options {
      min = 80
      max = 80
    }
  }
}
resource "oci_core_subnet" "product" {
  compartment_id    = var.compartment_ocid
  vcn_id            = oci_core_vcn.product.id
  cidr_block        = "10.86.0.0/24"
  route_table_id    = oci_core_route_table.product.id
  security_list_ids = [oci_core_security_list.product.id]
}
