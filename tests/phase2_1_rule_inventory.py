#!/usr/bin/env python
"""
Phase 2.1 - Rule Inventory for Normas APA 7 System.

Inventory of all 37 rules with their details for functional audit.
"""

import sys
sys.path.insert(0, r'C:\Users\USER\Desktop\normas_apa')

from backend.app.rules.registry import get_rules
from backend.app.rules.base import Rule, Category, ValidationStatus, Severity

rules = get_rules()

print("=" * 80)
print("PHASE 2.1 - RULE INVENTORY")
print("=" * 80)
print(f"Total rules: {len(rules)}")
print()

# Inventory table
print("| ID         | Name                                     | File                  | Category          | Status      |")
print("|------------|------------------------------------------|-----------------------|-------------------|-------------|")

for r in rules:
    # Determine file from class module
    file_map = {
        'formatting': 'backend/app/rules/formatting.py',
        'citations': 'backend/app/rules/citations.py',
        'headings': 'backend/app/rules/headings.py',
        'references': 'backend/app/rules/references.py',
        'ref_format': 'backend/app/rules/ref_format.py',
        'cite_format': 'backend/app/rules/cite_format.py',
        'matching': 'backend/app/rules/matching.py',
        'tables': 'backend/app/rules/tables.py',
    }
    module_parts = r.__class__.__module__.split('.')
    file_part = module_parts[-1] if module_parts else 'unknown'
    
    # Get exceptions
    exceptions = str(getattr(r, 'exceptions', ''))[:60] if hasattr(r, 'exceptions') else 'N/A'
    
    # Determine status
    has_check = hasattr(r, 'check')
    origin = getattr(r, 'origin', 'apa7')
    
    row = f"| {r.id:8s} | {r.name[:30]:30s} | {file_part:23s} | {str(r.category):15s} | {origin:11s} |"
    print(row)

print()
print("=" * 80)
print(f"Total: {len(rules)} rules inventory complete")
print("=" * 80)

# Detailed inspection
print("\n--- DETAILED INSPECTION ---")
for r in rules:
    print(f"\nRule: {r.id} - {r.name}")
    print(f"  Class: {r.__class__.__name__}")
    print(f"  Module: {r.__class__.__module__}")
    print(f"  Category: {r.category}")
    print(f"  Origin: {getattr(r, 'origin', 'N/A')}")
    print(f"  Has check method: {hasattr(r, 'check')}")
    print(f"  Exceptions: {str(getattr(r, 'exceptions', ''))[:80]}")
    print(f"  Description: {r.description[:80] if r.description else 'N/A'}")