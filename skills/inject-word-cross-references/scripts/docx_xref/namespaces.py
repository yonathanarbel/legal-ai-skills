from __future__ import annotations

from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML = "http://www.w3.org/XML/1998/namespace"
NS = {"w": W}


def qn(name: str) -> str:
    prefix, local = name.split(":", 1)
    namespace = {"w": W, "xml": XML}[prefix]
    return f"{{{namespace}}}{local}"


PARSER = etree.XMLParser(resolve_entities=False, remove_blank_text=False, huge_tree=False)
