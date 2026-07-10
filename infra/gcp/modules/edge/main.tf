# Public edge module for the XRIQ GCP staging-devnet.
#
# A global external HTTPS load balancer in front of the private node VM, with a
# Google-managed TLS certificate and a Cloud Armor policy that:
#   - rate-limits per client IP,
#   - allows only safe read methods (GET/HEAD/OPTIONS), blocking all mutations
#     (which are POST: wallet transfers, block production, signed submit),
#   - blocks the admin endpoints entirely.
#
# This makes the API PUBLICLY REACHABLE. It is gated by enable_public_edge
# (default false in the root module) so it is never created unless a human
# explicitly opts in and supplies a domain. The managed certificate provisions
# only after the domain's DNS A record points at the load balancer IP.

variable "project_id" {
  type = string
}

variable "name_prefix" {
  type = string
}

variable "zone" {
  type = string
}

variable "network_id" {
  type = string
}

variable "vm_self_link" {
  type = string
}

variable "api_domain" {
  description = "Fully-qualified domain for the public API edge (managed TLS cert). Its DNS A record must point at the edge IP output."
  type        = string
}

variable "rate_limit_per_minute" {
  description = "Per-client-IP request rate limit at the edge."
  type        = number
}

resource "google_compute_global_address" "edge" {
  project = var.project_id
  name    = "${var.name_prefix}-edge-ip"
}

resource "google_compute_managed_ssl_certificate" "edge" {
  project = var.project_id
  name    = "${var.name_prefix}-edge-cert"

  managed {
    domains = [var.api_domain]
  }
}

resource "google_compute_health_check" "edge" {
  project             = var.project_id
  name                = "${var.name_prefix}-edge-hc"
  check_interval_sec  = 15
  timeout_sec         = 5
  healthy_threshold   = 2
  unhealthy_threshold = 3

  http_health_check {
    port         = 8090
    request_path = "/api/v1/health"
  }
}

resource "google_compute_instance_group" "edge" {
  project   = var.project_id
  name      = "${var.name_prefix}-edge-ig"
  zone      = var.zone
  instances = [var.vm_self_link]

  named_port {
    name = "http"
    port = 8090
  }
}

resource "google_compute_security_policy" "edge" {
  project = var.project_id
  name    = "${var.name_prefix}-edge-armor"

  # Block all mutating methods (mutations are POST); only read methods pass.
  rule {
    action   = "deny(403)"
    priority = 800
    match {
      expr {
        expression = "!(request.method == 'GET' || request.method == 'HEAD' || request.method == 'OPTIONS')"
      }
    }
    description = "read-only edge: block non-GET methods (all mutations)"
  }

  # Keep admin endpoints off the public edge entirely.
  rule {
    action   = "deny(403)"
    priority = 810
    match {
      expr {
        expression = "request.path.startsWith('/api/v1/admin')"
      }
    }
    description = "block admin endpoints at the public edge"
  }

  # Per-IP rate limit.
  rule {
    action   = "throttle"
    priority = 1000
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
    rate_limit_options {
      conform_action = "allow"
      exceed_action  = "deny(429)"
      enforce_on_key = "IP"
      rate_limit_threshold {
        count        = var.rate_limit_per_minute
        interval_sec = 60
      }
    }
    description = "per-client-IP rate limit"
  }

  rule {
    action   = "allow"
    priority = 2147483647
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
    description = "default allow"
  }
}

resource "google_compute_backend_service" "edge" {
  project               = var.project_id
  name                  = "${var.name_prefix}-edge-backend"
  protocol              = "HTTP"
  port_name             = "http"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  timeout_sec           = 30
  health_checks         = [google_compute_health_check.edge.id]
  security_policy       = google_compute_security_policy.edge.id

  backend {
    group           = google_compute_instance_group.edge.id
    balancing_mode  = "UTILIZATION"
    max_utilization = 0.8
    capacity_scaler = 1.0
  }
}

resource "google_compute_url_map" "edge" {
  project         = var.project_id
  name            = "${var.name_prefix}-edge-urlmap"
  default_service = google_compute_backend_service.edge.id
}

resource "google_compute_target_https_proxy" "edge" {
  project          = var.project_id
  name             = "${var.name_prefix}-edge-https-proxy"
  url_map          = google_compute_url_map.edge.id
  ssl_certificates = [google_compute_managed_ssl_certificate.edge.id]
}

resource "google_compute_global_forwarding_rule" "edge" {
  project               = var.project_id
  name                  = "${var.name_prefix}-edge-fr"
  target                = google_compute_target_https_proxy.edge.id
  port_range            = "443"
  ip_address            = google_compute_global_address.edge.address
  load_balancing_scheme = "EXTERNAL_MANAGED"
}

# Allow the Google Front End / health-check ranges to reach the VM on 8090.
resource "google_compute_firewall" "edge" {
  project   = var.project_id
  name      = "${var.name_prefix}-allow-edge"
  network   = var.network_id
  direction = "INGRESS"

  allow {
    protocol = "tcp"
    ports    = ["8090"]
  }

  source_ranges = ["130.211.0.0/22", "35.191.0.0/16"]
  target_tags   = ["xriq-node"]
}

output "edge_ip" {
  value = google_compute_global_address.edge.address
}

output "api_url" {
  value = "https://${var.api_domain}"
}
