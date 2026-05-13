"""
Vendor spreadsheet intake → ServiceNow Normal Change wizard.

Subpackages:
- vendor_mappings/   per-vendor rule sets (currently: epsilon)
- mapping_spec.py    FieldRule / VendorMapping / VENDORS registry
- excel_parser.py    openpyxl-backed cell + sheet reader
- mapping_apply.py   applies a VendorMapping to a parsed payload
"""
