# Billing (Stripe)

## Grace period (dunning)

Configure `BILLING_GRACE_PERIOD_DAYS` in the backend environment (default `3`, max `30`). Typical production values are **3–7 days**.

On `invoice.payment_failed`, the webhook sets `subscription_status=past_due` and starts a grace window. After it expires, mutating API calls return **402** until payment is fixed (`assert_workspace_billing_allows_writes`).

## Customer portal

**Update card** and **cancel subscription** use Stripe **Billing Portal**. Enable the actions you need under Stripe Dashboard → **Settings → Billing → Customer portal** (payment methods, cancellation, etc.).

## Webhooks

Register at least: `checkout.session.completed`, `invoice.paid`, `invoice.payment_failed`, `customer.subscription.updated`, `customer.subscription.deleted`.

## Invoices (PDF)

`GET /api/v1/billing/invoices` lists Stripe invoices for the workspace customer (`invoice_pdf`, `hosted_invoice_url`). Requires **owner/admin**; `GET /billing/subscription` is readable by **all workspace roles** so dunning banners work for everyone.
