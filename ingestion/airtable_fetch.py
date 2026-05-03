"""
Airtable API client for Botanical Medicine Repertory

Fetches botanical records from Airtable with pagination and rate limiting.
"""

import os
import time
import json
import logging
from typing import List, Dict, Optional, Iterator
from dataclasses import dataclass
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib.parse import urljoin


logger = logging.getLogger(__name__)


@dataclass
class AirtableConfig:
    """Configuration for Airtable API."""
    base_id: str
    table_id: str
    api_key: str
    rate_limit_per_second: float = 5.0
    max_retries: int = 3
    timeout: int = 30


class AirtableClient:
    """
    Client for fetching records from Airtable API.
    
    Handles:
    - Pagination (auto-fetch all records)
    - Rate limiting (5 requests/second max)
    - Retry logic for transient failures
    - Field mapping and data transformation
    """
    
    API_BASE = "https://api.airtable.com/v0/"
    
    def __init__(self, config: Optional[AirtableConfig] = None):
        """
        Initialize Airtable client.
        
        Args:
            config: AirtableConfig instance. If None, loads from config.json.
        """
        if config is None:
            config = self._load_config_from_file()
        
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json"
        })
        
        # Add retry adapter
        adapter = HTTPAdapter(max_retries=config.max_retries)
        self.session.mount('https://', adapter)
        
        # Rate limiting
        self._last_request_time = 0.0
        self._min_interval = 1.0 / config.rate_limit_per_second
    
    def _load_config_from_file(self) -> AirtableConfig:
        """Load configuration from project config.json."""
        config_path = Path(__file__).parent.parent / "config" / "config.json"
        
        with open(config_path, 'r') as f:
            data = json.load(f)
        
        airtable_config = data.get("airtable", {})
        api_key = os.environ.get(
            airtable_config.get("api_key_env", "AIRTABLE_API_KEY")
        )
        
        if not api_key:
            raise ValueError(
                f"Airtable API key not found. Set {airtable_config.get('api_key_env')} "
                "environment variable."
            )
        
        return AirtableConfig(
            base_id=airtable_config["base_id"],
            table_id=airtable_config["table_id"],
            api_key=api_key,
            rate_limit_per_second=airtable_config.get("rate_limit_per_second", 5.0)
        )
    
    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.time()
    
    def _make_request(self, url: str, params: Optional[Dict] = None) -> Dict:
        """Make a rate-limited request to Airtable API."""
        self._rate_limit()
        
        response = self.session.get(url, params=params, timeout=self.config.timeout)
        response.raise_for_status()
        
        return response.json()
    
    def fetch_records(
        self,
        fields: Optional[List[str]] = None,
        filter_formula: Optional[str] = None,
        max_records: Optional[int] = None
    ) -> Iterator[Dict]:
        """
        Fetch all records from Airtable with automatic pagination.
        
        Args:
            fields: Specific fields to retrieve (None = all)
            filter_formula: Airtable formula for filtering records
            max_records: Maximum records to fetch (None = all)
        
        Yields:
            Record dictionaries with 'id' and 'fields'
        """
        url = urljoin(self.API_BASE, f"{self.config.base_id}/{self.config.table_id}")
        
        params = {}
        if fields:
            # Airtable API uses 'fields[]' for multiple fields
            params["fields"] = fields
        if filter_formula:
            params["filterByFormula"] = filter_formula
        
        offset = None
        record_count = 0
        page = 0
        
        logger.info(f"Starting fetch from {url}")
        
        while True:
            if offset:
                params["offset"] = offset
            
            try:
                data = self._make_request(url, params)
                page += 1
                
                records = data.get("records", [])
                logger.debug(f"Page {page}: fetched {len(records)} records")
                
                for record in records:
                    yield record
                    record_count += 1
                    
                    if max_records and record_count >= max_records:
                        logger.info(f"Reached max_records limit: {max_records}")
                        return
                
                # Check for more pages
                offset = data.get("offset")
                if not offset:
                    break
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed: {e}")
                raise
        
        logger.info(f"Fetch complete. Total records: {record_count}")
    
    def fetch_all_records(
        self,
        fields: Optional[List[str]] = None,
        filter_formula: Optional[str] = None,
        max_records: Optional[int] = None
    ) -> List[Dict]:
        """
        Fetch all records as a list (convenience method).
        
        WARNING: This loads all records into memory. For large datasets,
        use fetch_records() as an iterator instead.
        """
        return list(self.fetch_records(fields, filter_formula, max_records))
    
    def get_record(self, record_id: str) -> Dict:
        """
        Fetch a single record by ID.
        
        Args:
            record_id: Airtable record ID
        
        Returns:
            Record dictionary
        """
        url = urljoin(
            self.API_BASE,
            f"{self.config.base_id}/{self.config.table_id}/{record_id}"
        )
        
        return self._make_request(url)
    
    def get_table_schema(self) -> Dict:
        """
        Get table schema information.
        
        Returns:
            Schema dictionary with field definitions
        """
        url = urljoin(self.API_BASE, f"meta/bases/{self.config.base_id}/tables")
        
        data = self._make_request(url)
        
        # Find our specific table
        for table in data.get("tables", []):
            if table.get("id") == self.config.table_id:
                return table
        
        raise ValueError(f"Table {self.config.table_id} not found in base")
    
    def inspect_fields(self) -> List[Dict]:
        """
        Get list of available fields with their types.
        
        Returns:
            List of field definitions
        """
        schema = self.get_table_schema()
        fields = schema.get("fields", [])
        
        return [
            {
                "name": f.get("name"),
                "type": f.get("type"),
                "options": f.get("options", {})
            }
            for f in fields
        ]
    
    def sample_record(self) -> Optional[Dict]:
        """
        Fetch a single sample record for inspection.
        
        Returns:
            First record or None if table is empty
        """
        records = self.fetch_all_records(max_records=1)
        return records[0] if records else None


def save_records_to_json(records: List[Dict], filepath: str):
    """Save fetched records to JSON file."""
    with open(filepath, 'w') as f:
        json.dump(records, f, indent=2)
    logger.info(f"Saved {len(records)} records to {filepath}")


def main():
    """CLI for testing Airtable connection."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Fetch botanical data from Airtable")
    parser.add_argument("--inspect", action="store_true", help="List available fields")
    parser.add_argument("--sample", action="store_true", help="Fetch one sample record")
    parser.add_argument("--output", "-o", help="Output JSON file")
    parser.add_argument("--max", type=int, help="Maximum records to fetch")
    parser.add_argument("--fields", help="Comma-separated field names")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    client = AirtableClient()
    
    if args.inspect:
        print("\n=== Airtable Fields ===")
        fields = client.inspect_fields()
        for f in fields:
            print(f"  {f['name']}: {f['type']}")
            if f['options']:
                print(f"    Options: {f['options']}")
        print()
    
    elif args.sample:
        print("\n=== Sample Record ===")
        record = client.sample_record()
        if record:
            print(json.dumps(record, indent=2))
        else:
            print("No records found")
        print()
    
    else:
        # Full fetch
        fields = args.fields.split(",") if args.fields else None
        
        print(f"\nFetching records{' (limited to ' + str(args.max) + ')' if args.max else ''}...")
        records = client.fetch_all_records(fields=fields, max_records=args.max)
        print(f"Fetched {len(records)} records")
        
        if args.output:
            save_records_to_json(records, args.output)
        else:
            # Print first record as preview
            if records:
                print("\n=== First Record Preview ===")
                preview = {
                    "id": records[0].get("id"),
                    "fields": {
                        k: v for k, v in records[0].get("fields", {}).items()
                        if not isinstance(v, (list, dict)) or len(str(v)) < 100
                    }
                }
                print(json.dumps(preview, indent=2))


if __name__ == "__main__":
    main()