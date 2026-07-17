import pytest
from app.parser import parse_pdf, detect_level, build_tree

def test_out_of_order_sections():
    """Section 3.4 appears before 3.3 in the PDF - both must exist"""
    nodes = parse_pdf("data/ct200_manual.pdf")
    headings = [n["heading"] for n in nodes]
    has_34 = any("3.4" in h for h in headings)
    has_33 = any("3.3" in h for h in headings)
    assert has_34 and has_33, "Both 3.3 and 3.4 must be parsed even if out of order"

def test_deep_nested_heading():
    """2.1.1.1 is 4 levels deep with no 2.1.1 parent"""
    nodes = parse_pdf("data/ct200_manual.pdf")
    deep = [n for n in nodes if "2.1.1.1" in n["heading"]]
    assert len(deep) > 0, "Section 2.1.1.1 must be parsed"
    assert deep[0]["level"] == 4, "2.1.1.1 must be level 4"

def test_duplicate_heading_titles():
    """Error Codes appears as both 4.2 and 7.1 - must be two distinct nodes"""
    nodes = parse_pdf("data/ct200_manual.pdf")
    error_code_nodes = [n for n in nodes if "Error Codes" in n["heading"]]
    assert len(error_code_nodes) >= 2, "Both 4.2 and 7.1 Error Codes sections must exist"
    paths = [n["path"] for n in error_code_nodes]
    assert len(set(paths)) == 2, "Duplicate heading titles must have different paths"

def test_v2_has_more_nodes():
    """V2 adds section 5.3 Data Export - must have more nodes than v1"""
    v1_nodes = parse_pdf("data/ct200_manual.pdf")
    v2_nodes = parse_pdf("data/ct200_manual_v2.pdf")
    assert len(v2_nodes) > len(v1_nodes), "V2 must have more nodes than V1"

def test_content_hash_changes_between_versions():
    """Battery life section changed between v1 and v2"""
    v1_nodes = parse_pdf("data/ct200_manual.pdf")
    v2_nodes = parse_pdf("data/ct200_manual_v2.pdf")
    v1_battery = next((n for n in v1_nodes if "2.1.1.1" in n["heading"]), None)
    v2_battery = next((n for n in v2_nodes if "2.1.1.1" in n["heading"]), None)
    assert v1_battery and v2_battery, "Battery section must exist in both versions"
    assert v1_battery["content_hash"] != v2_battery["content_hash"], "Hash must differ when content changes"