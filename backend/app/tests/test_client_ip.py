from django.test import RequestFactory, SimpleTestCase, override_settings

from app.client_ip import client_ip


def _request(forwarded=None, remote_addr="10.0.0.2", **extra):
    meta = {"REMOTE_ADDR": remote_addr, **extra}
    if forwarded is not None:
        meta["HTTP_X_FORWARDED_FOR"] = forwarded
    return RequestFactory().get("/", **meta)


class ClientIpTestCase(SimpleTestCase):
    def test_default_is_one_trusted_proxy(self):
        self.assertEqual("203.0.113.7", client_ip(_request("203.0.113.7")))

    def test_spoofed_entries_left_of_the_proxy_hop_are_ignored(self):
        request = _request("198.51.100.1, 192.0.2.9, 203.0.113.7")
        self.assertEqual("203.0.113.7", client_ip(request))

    def test_spoofed_cf_header_is_ignored(self):
        request = _request("203.0.113.7", HTTP_CF_CONNECTING_IP="198.51.100.1")
        self.assertEqual("203.0.113.7", client_ip(request))

    def test_no_forwarded_header_uses_remote_addr(self):
        self.assertEqual("10.0.0.2", client_ip(_request()))
        self.assertEqual("10.0.0.2", client_ip(_request(" , ")))

    @override_settings(TRUSTED_PROXY_COUNT=0)
    def test_zero_trusted_proxies_ignores_the_header(self):
        self.assertEqual("10.0.0.2", client_ip(_request("203.0.113.7")))

    @override_settings(TRUSTED_PROXY_COUNT=2)
    def test_two_trusted_proxies_take_the_second_entry_from_the_right(self):
        request = _request("198.51.100.1, 203.0.113.7, 172.16.0.5")
        self.assertEqual("203.0.113.7", client_ip(request))

    @override_settings(TRUSTED_PROXY_COUNT=2)
    def test_fewer_entries_than_hops_uses_the_left_most(self):
        self.assertEqual("203.0.113.7", client_ip(_request("203.0.113.7")))
