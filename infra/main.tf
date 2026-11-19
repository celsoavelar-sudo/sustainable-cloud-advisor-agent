terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_project_service" "required_apis" {
  for_each = toset([
    "aiplatform.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudtrace.googleapis.com",
    "logging.googleapis.com",
  ])
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_service_account" "advisor_runtime" {
  account_id   = "sustainable-cloud-advisor-sa"
  display_name = "Sustainable Cloud Advisor Runtime SA"
  project      = var.project_id
  depends_on   = [google_project_service.required_apis]
}

resource "google_secret_manager_secret" "advisor_config_secret" {
  secret_id = "sustainable-cloud-advisor-config"
  project   = var.project_id
  replication {
    auto {}
  }
  depends_on = [google_project_service.required_apis]
}

resource "google_secret_manager_secret_iam_member" "advisor_secret_accessor" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.advisor_config_secret.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.advisor_runtime.email}"
}
