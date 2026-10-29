import unittest
from email import message_from_string

from helpdesk.overrides.email_account import is_auto_reply


def mail(*headers):
    return message_from_string("\n".join([*headers, "Subject: x", "", "body"]))


class TestAutoReply(unittest.TestCase):
    def test_replies_are_skipped(self):
        self.assertTrue(is_auto_reply(mail("Auto-Submitted: auto-replied")))
        self.assertTrue(is_auto_reply(mail("Auto-Submitted: Auto-Replied; owner=x")))
        self.assertTrue(is_auto_reply(mail("X-Autoreply: yes")))
        self.assertTrue(is_auto_reply(mail("X-Autorespond: yes")))
        self.assertTrue(is_auto_reply(mail("Precedence: auto_reply")))

    def test_other_mail_still_becomes_a_ticket(self):
        self.assertFalse(is_auto_reply(mail()))
        self.assertFalse(is_auto_reply(mail("Auto-Submitted: no")))
        self.assertFalse(is_auto_reply(mail("Auto-Submitted: auto-generated")))
        self.assertFalse(is_auto_reply(mail("Precedence: bulk")))
        self.assertFalse(is_auto_reply(mail("X-Autoreply: no")))
