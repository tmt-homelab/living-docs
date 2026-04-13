#!/usr/bin/env python3
"""
Fetch documentation data from Corvus and run sync_corvus.py.

This script queries the Corvus API for:
- Services (from CMDB)
- Active Incidents
- Active Change Windows

Then passes the data to sync_corvus.py to regenerate documentation pages.
"""

import json
import os
import sys
import httpx
import asyncio

# Add the script directory to path for importing sync_corvus
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sync_corvus import sync

# Configuration - In production, these would be env vars
CORVUS_URL = os.getenv("CORVUS_URL", "http://localhost:9420")
CORVUS_API_KEY = os.getenv("CORVUS_API_KEY", "")


async def fetch_services(client: httpx.AsyncClient) -> list:
    """Fetch all services from Corvus CMDB."""
    print("Fetching services from Corvus CMDB...")
    try:
        # Use /ops/cmdb endpoint (list all services)
        resp = await client.get("/ops/cmdb")
        resp.raise_for_status()
        services = resp.json()
        print(f"  Found {len(services)} services")
        return services
    except Exception as e:
        print(f"  Error fetching services: {e}")
        return []


async def fetch_active_incidents(client: httpx.AsyncClient) -> list:
    """Fetch active incidents from Corvus."""
    print("Fetching active incidents...")
    try:
        # Use /ops/incidents with status=open filter
        resp = await client.get("/ops/incidents", params={"status": "open"})
        resp.raise_for_status()
        incidents = resp.json()
        print(f"  Found {len(incidents)} active incidents")
        return incidents
    except Exception as e:
        print(f"  Error fetching incidents: {e}")
        return []


async def fetch_active_changes(client: httpx.AsyncClient) -> list:
    """Fetch active change windows from Corvus."""
    print("Fetching active change windows...")
    try:
        # Use /ops/changes with status=active filter
        resp = await client.get("/ops/changes", params={"status": "active"})
        resp.raise_for_status()
        changes = resp.json()
        print(f"  Found {len(changes)} active changes")
        return changes
    except Exception as e:
        print(f"  Error fetching changes: {e}")
        return []


async def main():
    """Main sync function."""
    headers = {"Authorization": f"Bearer {CORVUS_API_KEY}"} if CORVUS_API_KEY else {}
    
    async with httpx.AsyncClient(base_url=CORVUS_URL, headers=headers, timeout=30.0) as client:
        # Health check
        try:
            health_resp = await client.get("/health")
            health_resp.raise_for_status()
            print(f"Corvus health check OK: {CORVUS_URL}")
        except Exception as e:
            print(f"Warning: Corvus health check failed: {e}")
            print("Continuing with empty data...")
        
        # Fetch all data
        services = await fetch_services(client)
        incidents = await fetch_active_incidents(client)
        changes = await fetch_active_changes(client)
        
        # Run the sync
        print(f"\nRunning documentation sync with {len(services)} services...")
        sync(services, incidents, changes)
        print("Sync completed successfully.")


if __name__ == "__main__":
    asyncio.run(main())
