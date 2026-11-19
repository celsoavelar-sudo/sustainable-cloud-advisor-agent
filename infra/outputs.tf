output "runtime_service_account_email" {
  value       = google_service_account.advisor_runtime.email
  description = "Service account for Sustainable Cloud Advisor"
}

output "advisor_config_secret_id" {
  value       = google_secret_manager_secret.advisor_config_secret.secret_id
  description = "Secret Manager secret ID"
}
