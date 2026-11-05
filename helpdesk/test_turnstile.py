from unittest.mock import patch

import frappe
import requests
from frappe.tests import IntegrationTestCase

from helpdesk.turnstile import verify_login_token


class TestTurnstile(IntegrationTestCase):
	def setUp(self):
		frappe.conf.turnstile_secret_key = "secret"
		frappe.local.form_dict = frappe._dict()

	def tearDown(self):
		frappe.conf.pop("turnstile_secret_key", None)

	def test_off_without_secret(self):
		frappe.conf.pop("turnstile_secret_key")
		verify_login_token()

	def test_missing_token_is_refused(self):
		self.assertRaises(frappe.AuthenticationError, verify_login_token)

	def test_rejected_token_is_refused(self):
		frappe.local.form_dict["cf-turnstile-response"] = "x"
		with patch("helpdesk.turnstile.requests.post") as post:
			post.return_value.status_code = 200
			post.return_value.json.return_value = {"success": False}
			self.assertRaises(frappe.AuthenticationError, verify_login_token)

	def test_oversized_token_is_refused(self):
		frappe.local.form_dict["cf-turnstile-response"] = "x" * 3000
		self.assertRaises(frappe.AuthenticationError, verify_login_token)

	def test_unreadable_answer_is_refused(self):
		frappe.local.form_dict["cf-turnstile-response"] = "x"
		with patch("helpdesk.turnstile.requests.post") as post:
			post.return_value.status_code = 200
			post.return_value.json.side_effect = ValueError
			self.assertRaises(frappe.AuthenticationError, verify_login_token)

	def test_client_error_from_cloudflare_is_refused(self):
		frappe.local.form_dict["cf-turnstile-response"] = "x"
		with patch("helpdesk.turnstile.requests.post") as post:
			post.return_value.status_code = 403
			post.return_value.json.return_value = {"error-codes": ["invalid-input-secret"]}
			self.assertRaises(frappe.AuthenticationError, verify_login_token)

	def test_server_error_from_cloudflare_lets_the_login_through(self):
		frappe.local.form_dict["cf-turnstile-response"] = "x"
		with patch("helpdesk.turnstile.requests.post") as post:
			post.return_value.status_code = 503
			verify_login_token()

	def test_accepted_token_passes(self):
		frappe.local.form_dict["cf-turnstile-response"] = "x"
		with patch("helpdesk.turnstile.requests.post") as post:
			post.return_value.status_code = 200
			post.return_value.json.return_value = {"success": True}
			verify_login_token()

	def test_outage_lets_the_login_through(self):
		frappe.local.form_dict["cf-turnstile-response"] = "x"
		with patch("helpdesk.turnstile.requests.post", side_effect=requests.ConnectionError):
			verify_login_token()
