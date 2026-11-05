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

	A missing or rejected token stops the login. If Cloudflare gives no answer (network error, timeout, 5xx) the login goes on and the
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
	except (requests.ConnectionError, requests.Timeout):  # no answer from Cloudflare: the login goes on
		frappe.log_error("Turnstile siteverify tidak dapat dihubungi; login diteruskan", "Turnstile")
		return
	if response.status_code >= 500:  # Cloudflare failing on its side
		frappe.log_error(f"Turnstile siteverify menjawab {response.status_code}; login diteruskan", "Turnstile")
		return
	try:
		success = response.json().get("success") is True
	except ValueError:  # an answer we cannot read, or a 4xx, is not a pass
		success = False
	if not success:
		frappe.throw("Pemeriksaan keamanan gagal. Muat ulang halaman lalu coba lagi.", frappe.AuthenticationError)
