"""
Vendor-agnostic mapping spec.

A `VendorMapping` is a registered set of `FieldRule`s describing how cells
and named sheets in an uploaded spreadsheet map to ServiceNow change_request
fields. Each rule carries a UI-visible `source_rule` explaining where the
value came from, a `kind` driving the badge + AI button rendering, and an
`extractor` callable that pulls the proposed value out of a parsed payload.

Kinds:
- 'auto'          : value derived deterministically from the spreadsheet
- 'ai-candidate'  : leave blank; engineer or AI fills it in
- 'human-input'   : engineer fills manually; AI generate is available as
                    a stub (per the locked decision in the plan)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List


@dataclass
class ParsedPayload:
    cells: Dict[str, str] = field(default_factory=dict)
    cell_labels: Dict[str, str] = field(default_factory=dict)
    sheets: Dict[str, str] = field(default_factory=dict)
    first_sheet_name: str = ''


FieldKind = str  # 'auto' | 'ai-candidate' | 'human-input'


@dataclass
class FieldRule:
    target_field: str
    source_rule: str
    kind: FieldKind
    group: str = ''
    extractor: Callable[[ParsedPayload], str] = lambda _p: ''
    label: str = ''


@dataclass
class VendorMapping:
    name: str
    rules: List[FieldRule]

    def rules_by_field(self) -> Dict[str, FieldRule]:
        return {r.target_field: r for r in self.rules}


VENDORS: Dict[str, VendorMapping] = {}


def register(slug: str, mapping: VendorMapping) -> None:
    VENDORS[slug] = mapping


def get_mapping(slug: str) -> VendorMapping | None:
    return VENDORS.get(slug)


# Trigger vendor registration on package import.
from .vendor_mappings import epsilon as _epsilon  # noqa: F401,E402
