from __future__ import annotations

import os
import tempfile
import zipfile
from collections import OrderedDict
from pathlib import Path

from lxml import etree

from .namespaces import PARSER


class DocxPackage:
    """In-memory package that preserves untouched entries and ZIP ordering."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._infos: list[zipfile.ZipInfo] = []
        self._data: OrderedDict[str, bytes] = OrderedDict()
        with zipfile.ZipFile(self.path, "r") as source:
            for info in source.infolist():
                if info.filename in self._data:
                    raise ValueError(f"Duplicate ZIP entry is unsupported: {info.filename}")
                self._infos.append(info)
                self._data[info.filename] = source.read(info.filename)

    def names(self) -> list[str]:
        return list(self._data)

    def has(self, name: str) -> bool:
        return name in self._data

    def read(self, name: str) -> bytes:
        try:
            return self._data[name]
        except KeyError as exc:
            raise ValueError(f"DOCX part not found: {name}") from exc

    def xml(self, name: str) -> etree._Element:
        return etree.fromstring(self.read(name), parser=PARSER)

    def replace_xml(self, name: str, root: etree._Element) -> None:
        original = self.read(name)
        declaration = original.lstrip().startswith(b"<?xml")
        standalone = None
        try:
            standalone = root.getroottree().docinfo.standalone
        except (AttributeError, ValueError):
            pass
        kwargs: dict = {"encoding": "UTF-8", "xml_declaration": declaration}
        if standalone in (True, False):
            kwargs["standalone"] = standalone
        self._data[name] = etree.tostring(root, **kwargs)

    def write(self, destination: Path) -> None:
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(
            prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
        )
        os.close(handle)
        try:
            with zipfile.ZipFile(temporary, "w") as output:
                for info in self._infos:
                    output.writestr(info, self._data[info.filename])
            os.replace(temporary, destination)
        except Exception:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise
