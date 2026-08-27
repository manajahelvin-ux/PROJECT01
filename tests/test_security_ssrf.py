"""
Tests for the scraping security module — Anti-SSRF protection.
"""

import pytest
from django.test import TestCase

from apps.scraping.services import validate_url_safety, extract_with_selector


class TestAntiSSRF(TestCase):
    """Test SSRF protection blocks dangerous URLs."""

    def test_block_localhost(self):
        ok, _ = validate_url_safety("http://localhost/admin")
        self.assertFalse(ok)

    def test_block_127(self):
        ok, _ = validate_url_safety("http://127.0.0.1/test")
        self.assertFalse(ok)

    def test_block_ipv6_localhost(self):
        ok, _ = validate_url_safety("http://[::1]/test")
        self.assertFalse(ok)

    def test_block_cloud_metadata(self):
        ok, _ = validate_url_safety("http://169.254.169.254/latest/meta-data/")
        self.assertFalse(ok)

    def test_block_private_ip(self):
        ok, _ = validate_url_safety("http://192.168.1.1/admin")
        self.assertFalse(ok)

    def test_block_0000(self):
        ok, _ = validate_url_safety("http://0.0.0.0/test")
        self.assertFalse(ok)

    def test_allow_public_url(self):
        ok, _ = validate_url_safety("https://example.com/products")
        self.assertTrue(ok)

    def test_block_ftp(self):
        ok, _ = validate_url_safety("ftp://example.com/file")
        self.assertFalse(ok)


class TestSelectors(TestCase):
    """Test CSS, XPath, and Regex extraction."""

    def test_css_selector(self):
        html = '<div class="product"><h2 class="title">Widget</h2><span class="price">29.99</span></div>'
        results = extract_with_selector(html, "h2.title", "css")
        self.assertEqual(results, ["Widget"])

    def test_css_multiple(self):
        html = '<ul><li class="item">A</li><li class="item">B</li><li class="item">C</li></ul>'
        results = extract_with_selector(html, "li.item", "css")
        self.assertEqual(len(results), 3)

    def test_css_attribute(self):
        html = '<a href="https://example.com" class="link">Click</a>'
        results = extract_with_selector(html, "a.link", "css", "href")
        self.assertEqual(results, ["https://example.com"])

    def test_regex_selector(self):
        html = '<p>Price: $49.99 and $29.99</p>'
        results = extract_with_selector(html, r"\$[\d.]+", "regex")
        self.assertEqual(len(results), 2)
        self.assertIn("$49.99", results)

    def test_empty_result(self):
        html = '<p>No products here</p>'
        results = extract_with_selector(html, ".product", "css")
        self.assertEqual(results, [])
