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

# OIDC (Hydra) — preferred auth path. When HYDRA_CLIENT_ID + HYDRA_CLIENT_SECRET
# are set, mint a short-lived JWT against Hydra and use it as Bearer; falls back
# to CORVUS_API_KEY if either is missing (dual-mode friendly during migration).
HYDRA_TOKEN_URL = os.getenv(
    "HYDRA_TOKEN_URL", "https://hydra.themillertribe-int.org/oauth2/token"
)
HYDRA_AUDIENCE = os.getenv("HYDRA_AUDIENCE", "corvus")
HYDRA_SCOPE = os.getenv("HYDRA_SCOPE", "corvus.read")
HYDRA_CLIENT_ID = os.getenv("HYDRA_CLIENT_ID", "")
HYDRA_CLIENT_SECRET = os.getenv("HYDRA_CLIENT_SECRET", "")


async def _mint_hydra_token() -> str:
    """Client-credentials grant against Hydra. Returns a bearer JWT."""
    async with httpx.AsyncClient(timeout=10.0) as c:
        resp = await c.post(
            HYDRA_TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "audience": HYDRA_AUDIENCE,
                "scope": HYDRA_SCOPE,
            },
            auth=(HYDRA_CLIENT_ID, HYDRA_CLIENT_SECRET),
        )
        resp.raise_for_status()
        token = resp.json().get("access_token")
        if not token:
            raise RuntimeError("Hydra token endpoint returned no access_token")
        return token


async def _build_auth_headers() -> dict[str, str]:
    """Pick auth method: Hydra OIDC if configured, else legacy API key."""
    if HYDRA_CLIENT_ID and HYDRA_CLIENT_SECRET:
        token = await _mint_hydra_token()
        print("Auth: OIDC (Hydra-issued JWT)")
        return {"Authorization": f"Bearer {token}"}
    if CORVUS_API_KEY:
        print("Auth: legacy API key (CORVUS_API_KEY)")
        return {"Authorization": f"Bearer {CORVUS_API_KEY}"}
    print("Auth: none (anonymous; reads will likely 401)")
    return {}


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
    headers = await _build_auth_headers()

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
