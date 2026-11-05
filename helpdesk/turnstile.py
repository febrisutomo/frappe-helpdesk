"""Cloudflare Turnstile on the login form.

Configured per site with `turnstile_site_key` and `turnstile_secret_key` in site_config.json; without them nothing
changes. The secret key never leaves the server; the site key is public and served to the login page script.
"""

import frappe
import requests

VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


@frappe.whitelist(allow_guest=True)
def site_key():
	"""Public key for the widget; empty when Turnstile is not configured for this site."""
	return frappe.conf.get("turnstile_site_key") if frappe.conf.get("turnstile_secret_key") else None


def verify_login_token(login_manager=None):
	"""`before_login` hook (it runs before the password is checked): a login needs a Turnstile token that Cloudflare accepts.

	A missing or rejected token stops the login. If the request to Cloudflare itself fails (network error, timeout, HTTP error) the login goes on and the
	failure is logged, so an outage at Cloudflare does not lock the support team out.
	"""
	secret = frappe.conf.get("turnstile_secret_key")
	if not secret:
		return

	token = frappe.local.form_dict.get("cf-turnstile-response")
	if not isinstance(token, str) or not token or len(token) > 2048:
		frappe.throw("Selesaikan pemeriksaan keamanan lalu coba lagi.", frappe.AuthenticationError)
	try:
		response = requests.post(
			VERIFY_URL,
			data={"secret": secret, "response": token, "remoteip": frappe.local.request_ip},
			timeout=5,
		)
		response.raise_for_status()
	except requests.RequestException:  # Cloudflare unreachable or failing: only this case lets the login through
		frappe.log_error("Turnstile siteverify tidak dapat dihubungi; login diteruskan", "Turnstile")
		return
	try:
		success = response.json().get("success")
	except ValueError:  # an answer we cannot read is not a pass
		success = False
	if not success:
		frappe.throw("Pemeriksaan keamanan gagal. Muat ulang halaman lalu coba lagi.", frappe.AuthenticationError)
