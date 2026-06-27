output "budget_name" {
  value = aws_budgets_budget.awsforge_poc_budget.name
}

output "alert_email" {
  value = var.alert_email
}
