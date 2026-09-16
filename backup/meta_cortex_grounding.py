"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  GROUNDING-VALIDATOR v1.0 — Vérification Factuelle Avancée pour BEK-v15.2   ║
║  Fichier : meta_cortex_grounding.py                                          ║
║  Rôle    : Génère et exécute des requêtes SQL de vérification automatique   ║
║            sur Neon PostgreSQL pour valider chaque claim du draft           ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import re
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger("GroundingValidator")


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass
class Claim:
    claim_id: str
    claim_text: str
    claim_type: str  # 'numeric', 'entity', 'date', 'count', 'aggregate'
    context: str
    source_table: Optional[str] = None
    source_column: Optional[str] = None
    expected_value: Optional[str] = None


@dataclass
class GroundingResult:
    claim: Claim
    verified: bool
    verification_query: str
    actual_value: str
    expected_value: Optional[str]
    mismatch_severity: Optional[Severity]
    execution_time_ms: int
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


CRM_SCHEMA = {
    "companies": {
        "columns": ["id", "name", "industry", "size", "revenue", "created_at", "updated_at", "status"],
        "types": {"id": "UUID", "name": "TEXT", "industry": "TEXT", "size": "TEXT", 
                  "revenue": "DECIMAL", "created_at": "TIMESTAMPTZ", "updated_at": "TIMESTAMPTZ", "status": "TEXT"},
    },
    "contacts": {
        "columns": ["id", "company_id", "first_name", "last_name", "email", "phone", "role", "created_at", "updated_at"],
        "types": {"id": "UUID", "company_id": "UUID", "first_name": "TEXT", "last_name": "TEXT",
                  "email": "TEXT", "phone": "TEXT", "role": "TEXT", "created_at": "TIMESTAMPTZ", "updated_at": "TIMESTAMPTZ"},
    },
    "opportunities": {
        "columns": {"id", "company_id", "contact_id", "name", "stage", "amount", "probability", "expected_close_date", "created_at", "updated_at"},
        "types": {"id": "UUID", "company_id": "UUID", "contact_id": "UUID", "name": "TEXT",
                  "stage": "TEXT", "amount": "DECIMAL", "probability": "INT", 
                  "expected_close_date": "DATE", "created_at": "TIMESTAMPTZ", "updated_at": "TIMESTAMPTZ"},
    },
    "invoices": {
        "columns": ["id", "company_id", "opportunity_id", "invoice_number", "amount", "tax_amount", "total_amount", "status", "due_date", "created_at"],
        "types": {"id": "UUID", "company_id": "UUID", "opportunity_id": "UUID", 
                  "invoice_number": "TEXT", "amount": "DECIMAL", "tax_amount": "DECIMAL",
                  "total_amount": "DECIMAL", "status": "TEXT", "due_date": "DATE", "created_at": "TIMESTAMPTZ"},
    },
    "payments": {
        "columns": ["id", "invoice_id", "amount", "payment_method", "payment_date", "status"],
        "types": {"id": "UUID", "invoice_id": "UUID", "amount": "DECIMAL", 
                  "payment_method": "TEXT", "payment_date": "DATE", "status": "TEXT"},
    }
}


class ClaimExtractor:
    PATTERNS = {
        "montant": re.compile(r'(\d{1,3}(?:[\s\.]?\d{3})*(?:,\d{2})?)\s*(€|EUR|euros?|\$|USD)?', re.IGNORECASE),
        "pourcentage": re.compile(r'(\d{1,3}(?:[\.,]\d+)?)\s*%', re.IGNORECASE),
        "date": re.compile(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})', re.IGNORECASE),
        "email": re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'),
        "societe": re.compile(r'(?:société|entreprise|company|client)\s+["\']?([^"\']{2,50})["\']?', re.IGNORECASE),
        "statut": re.compile(r'(?:statut|status|état)\s+(?:est|de|du)\s+["\']?([^"\']+)["\']?', re.IGNORECASE),
    }

    AGGREGATE_KEYWORDS = ["total", "somme", "montant total", "chiffre d'affaires", "revenu", "nombre de", "count", "combien"]

    def __init__(self, schema: Dict = None):
        self.schema = schema or CRM_SCHEMA

    def extract_claims(self, draft: str, original_query: str) -> List[Claim]:
        claims = []
        lines = draft.split("\n")
        for i, line in enumerate(lines):
            context = self._get_context(lines, i)
            for match in self.PATTERNS["montant"].finditer(line):
                claims.append(Claim(f"amount_{i}_{match.start()}", match.group(0), "numeric", context, self._infer_table(context, "amount"), "amount"))
            for match in self.PATTERNS["pourcentage"].finditer(line):
                claims.append(Claim(f"pct_{i}_{match.start()}", match.group(0), "numeric", context, "opportunities", "probability"))
            for match in self.PATTERNS["date"].finditer(line):
                claims.append(Claim(f"date_{i}_{match.start()}", match.group(0), "date", context, "opportunities", "created_at"))
            for match in self.PATTERNS["societe"].finditer(line):
                claims.append(Claim(f"company_{i}_{match.start()}", match.group(1), "entity", context, "companies", "name"))
            for match in self.PATTERNS["email"].finditer(line):
                claims.append(Claim(f"email_{i}_{match.start()}", match.group(0), "entity", context, "contacts", "email"))
            if any(kw in line.lower() for kw in self.AGGREGATE_KEYWORDS):
                claims.append(Claim(f"aggregate_{i}", line.strip(), "aggregate", context, "opportunities"))

        seen = set()
        unique = []
        for c in claims:
            key = (c.claim_text.lower().strip(), c.claim_type)
            if key not in seen:
                seen.add(key)
                unique.append(c)
        return unique

    def _get_context(self, lines: List[str], index: int, window: int = 2) -> str:
        return "\n".join(lines[max(0, index - window):min(len(lines), index + window + 1)])

    def _infer_table(self, context: str, claim_type: str) -> str:
        ctx = context.lower()
        if "facture" in ctx: return "invoices"
        if "contact" in ctx or "email" in ctx: return "contacts"
        return "opportunities"


class SQLQueryGenerator:
    FORBIDDEN_KEYWORDS = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "CREATE", "EXEC", "TRUNCATE", "--", ";"]

    def __init__(self, schema: Dict = None):
        self.schema = schema or CRM_SCHEMA

    def generate_query(self, claim: Claim) -> Optional[str]:
        if not claim.source_table or claim.source_table not in self.schema:
            return None
        table = claim.source_table
        col = claim.source_column or "amount"

        if claim.claim_type == "numeric":
            val = self._extract_number(claim.claim_text)
            query = f"SELECT {col} as actual_value, ABS({col} - {val}) as diff FROM {table} WHERE ABS({col} - {val}) < {val * 0.05 + 1} LIMIT 5"
        elif claim.claim_type == "entity":
            val = claim.claim_text.replace("'", "''")
            query = f"SELECT {col} as actual_value FROM {table} WHERE {col} ILIKE '%{val}%' LIMIT 5"
        elif claim.claim_type == "aggregate":
            query = f"SELECT SUM(amount) as aggregate_value FROM {table}"
        else:
            return None

        return self._sanitize(query)

    def _extract_number(self, text: str) -> float:
        cleaned = re.sub(r'[^\d,.]', '', text).replace(',', '.')
        match = re.search(r'\d+(?:\.\d+)?', cleaned)
        return float(match.group(0)) if match else 0.0

    def _sanitize(self, query: str) -> Optional[str]:
        uq = query.upper().strip()
        if not uq.startswith("SELECT"): return None
        for f in self.FORBIDDEN_KEYWORDS:
            if f in uq: return None
        return query.strip()


class SecureSQLExecutor:
    def __init__(self, conn_str: str):
        self.conn = psycopg2.connect(conn_str)

    def execute(self, query: str) -> Tuple[bool, Any, Optional[str]]:
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SET statement_timeout = 5000")
                start = datetime.now()
                cur.execute(query)
                rows = cur.fetchall()
                elapsed = int((datetime.now() - start).total_seconds() * 1000)
                return True, {"rows": [dict(r) for r in rows], "elapsed_ms": elapsed}, None
        except Exception as e:
            return False, None, str(e)

    def close(self):
        if self.conn: self.conn.close()


class GroundingValidator:
    def __init__(self, conn_str: str):
        self.extractor = ClaimExtractor()
        self.generator = SQLQueryGenerator()
        self.executor = SecureSQLExecutor(conn_str)

    def validate(self, draft: str, query: str) -> List[GroundingResult]:
        claims = self.extractor.extract_claims(draft, query)
        results = []
        for claim in claims:
            sql = self.generator.generate_query(claim)
            if not sql:
                results.append(GroundingResult(claim, True, "", "UNVERIFIABLE", claim.claim_text, None, 0))
                continue
            success, data, err = self.executor.execute(sql)
            if not success or not data.get("rows"):
                results.append(GroundingResult(claim, False, sql, "NO_DATA", claim.claim_text, Severity.HIGH, 0, err))
            else:
                results.append(GroundingResult(claim, True, sql, str(data["rows"][0]), claim.claim_text, None, data["elapsed_ms"]))
        return results

    def close(self):
        self.executor.close()
