"""A tiny YAML loader/dumper sufficient for Fern docs configuration files."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Iterable, List, Tuple


@dataclass
class _Line:
    text: str
    indent: int


class YamlError(RuntimeError):
    """Raised when parsing of YAML input fails."""


class SimpleYaml:
    """Parses a limited subset of YAML that covers Fern docs configs."""

    indent_size = 2

    def __init__(self, lines: Iterable[str]):
        self.lines: List[_Line] = [
            _Line(text=line.rstrip("\n"), indent=len(line) - len(line.lstrip(" ")))
            for line in lines
        ]
        self.index = 0

    def parse(self) -> Any:
        value = self._parse_block(expected_indent=0)
        self._skip_blank_lines()
        if self.index != len(self.lines):
            raise YamlError("Unexpected trailing content in YAML input")
        return value

    def _peek(self) -> Tuple[int, _Line]:
        while self.index < len(self.lines):
            line = self.lines[self.index]
            if not line.text.strip() or line.text.lstrip().startswith("#"):
                self.index += 1
                continue
            return self.index, line
        return self.index, _Line(text="", indent=0)

    def _skip_blank_lines(self) -> None:
        while self.index < len(self.lines):
            text = self.lines[self.index].text.strip()
            if text and not text.startswith("#"):
                break
            self.index += 1

    def _parse_block(self, expected_indent: int) -> Any:
        collection: Any = None
        items_list: List[Any] = []
        mapping = OrderedDict()

        while True:
            saved_index = self.index
            index, line = self._peek()
            if index >= len(self.lines):
                break
            if line.indent < expected_indent:
                self.index = saved_index
                break
            if line.indent > expected_indent:
                raise YamlError("Unexpected indentation")
            text = line.text.strip()
            if text == "-" or text.startswith("- "):
                if collection not in (None, "list"):
                    raise YamlError("Cannot mix list and mapping items")
                collection = "list"
                self.index = index + 1
                value = self._parse_list_item(text[1:].lstrip(), expected_indent)
                items_list.append(value)
            else:
                if collection not in (None, "dict"):
                    raise YamlError("Cannot mix list and mapping items")
                collection = "dict"
                self.index = index + 1
                key, has_value, value_or_marker = self._parse_key_value(text)
                if not has_value:
                    value = self._parse_block(expected_indent + self.indent_size)
                elif value_or_marker == "__BLOCK__":
                    value = self._parse_block(expected_indent + self.indent_size)
                else:
                    value = value_or_marker
                mapping[key] = value
        if collection == "list":
            return items_list
        if collection == "dict":
            return mapping
        return OrderedDict()

    def _parse_list_item(self, text: str, parent_indent: int) -> Any:
        if not text:
            return self._parse_block(parent_indent + self.indent_size)
        if text.endswith(":"):
            key = text[:-1].strip()
            value = self._parse_block(parent_indent + self.indent_size)
            return OrderedDict([(key, value)])
        if ":" in text:
            key, remainder = text.split(":", 1)
            key = key.strip()
            remainder = remainder.strip()
            if remainder:
                value = _parse_scalar(remainder)
            else:
                value = self._parse_block(parent_indent + self.indent_size)
            mapping = OrderedDict([(key, value)])
            self._collect_additional_mapping_entries(mapping, parent_indent + self.indent_size)
            return mapping
        value = _parse_scalar(text.strip())
        self._collect_additional_mapping_entries(value, parent_indent + self.indent_size)
        return value

    def _collect_additional_mapping_entries(self, current: Any, indent: int) -> None:
        if not isinstance(current, OrderedDict):
            saved_index = self.index
            index, line = self._peek()
            if index < len(self.lines) and line.indent >= indent and not line.text.strip().startswith("- "):
                raise YamlError("Unexpected structure following scalar list item")
            self.index = saved_index
            return
        while True:
            saved_index = self.index
            index, line = self._peek()
            if index >= len(self.lines) or line.indent < indent:
                break
            if line.indent > indent:
                raise YamlError("Unexpected indentation in mapping")
            text = line.text.strip()
            if text.startswith("- "):
                break
            self.index = index + 1
            key, has_value, value_or_marker = self._parse_key_value(text)
            if not has_value:
                value = self._parse_block(indent + self.indent_size)
            elif value_or_marker == "__BLOCK__":
                value = self._parse_block(indent + self.indent_size)
            else:
                value = value_or_marker
            current[key] = value

    def _parse_key_value(self, text: str) -> Tuple[str, bool, Any]:
        if ":" not in text:
            raise YamlError(f"Invalid mapping entry: {text}")
        key, remainder = text.split(":", 1)
        key = key.strip()
        remainder = remainder.strip()
        if not remainder:
            return key, False, None
        if remainder == "|" or remainder == ">":
            raise YamlError("Multiline scalars are not supported")
        return key, True, _parse_scalar(remainder)


def load(text: str) -> Any:
    parser = SimpleYaml(text.splitlines())
    return parser.parse()


def dump(value: Any) -> str:
    return "\n".join(_dump_value(value, indent=0)).rstrip() + "\n"


def _dump_value(value: Any, indent: int) -> List[str]:
    prefix = " " * indent
    if isinstance(value, list):
        lines: List[str] = []
        for item in value:
            if isinstance(item, (list, OrderedDict)):
                lines.append(f"{prefix}-")
                lines.extend(_dump_value(item, indent + SimpleYaml.indent_size))
            else:
                lines.append(f"{prefix}- {_format_scalar(item)}")
        return lines
    if isinstance(value, OrderedDict):
        lines = []
        for key, item in value.items():
            if isinstance(item, (list, OrderedDict)):
                lines.append(f"{prefix}{key}:")
                lines.extend(_dump_value(item, indent + SimpleYaml.indent_size))
            else:
                lines.append(f"{prefix}{key}: {_format_scalar(item)}")
        return lines
    return [f"{prefix}{_format_scalar(value)}"]


def _format_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if not text:
        return "''"
    if any(ch in text for ch in "\n:#{}[]\"'@`") or text.strip() != text:
        escaped = text.replace("\\", "\\\\").replace("\"", "\\\"")
        return f'"{escaped}"'
    return text


def _parse_scalar(value: str) -> Any:
    if not value:
        return ""
    lowered = value.lower()
    if lowered == "null":
        return None
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        pass
    if (value.startswith("'") and value.endswith("'")) or (
        value.startswith('"') and value.endswith('"')
    ):
        return value[1:-1]
    return value

