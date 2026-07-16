"""Tests for intent label matching."""

from shared.eval.intent_matching import intent_labels_match, normalize_intent_label


def test_normalize_strips_thinking_and_case():
    assert normalize_intent_label("ADD_TO_CART") == "add_to_cart"
    assert normalize_intent_label("thinking...\nADD_PRODUCT") == "add_product"


def test_exact_and_case_insensitive():
    assert intent_labels_match("CANCEL_ORDER", "cancel_order")
    assert intent_labels_match("cancel_order", "cancel_order")


def test_add_product_synonyms():
    assert intent_labels_match("ADD_TO_CART", "add_product")
    assert intent_labels_match("ADD_ITEM", "add_product")
    assert intent_labels_match("add_item_to_cart", "add_product")
    assert intent_labels_match("ADD_ITEMS_TO_BASKET", "add_product")


def test_delivery_time_synonyms():
    assert intent_labels_match("track_delivery", "delivery_time")
    assert intent_labels_match("DELIVERY_DATE", "delivery_time")


def test_unrelated_intent_fails():
    assert not intent_labels_match("CANCEL_ORDER", "add_product")
    assert not intent_labels_match("", "add_product")
