import json
import sys
import httpx
import asyncio
from sync_corvus import sync

async def main():
    # Config - In production, these would be env vars
    CORVUS_URL = "http://dockp04:9420"
    CORVUS_API_KEY = sys.getenv("CORVUS_API_KEY", "")
    
    headers = {"Authorization": f"Bearer {CORVUS_API_KEY}"}
    
    async with httpx.AsyncClient(base_url=CORVUS_URL, headers=headers, timeout=30.0) as client:
        try:
            print("Fetching services from Corvus...")
            # Note: Assuming /ops/cmdb/all or similar exists based on the sync script's needs
            # If not, we might need to iterate or use a different endpoint.
            # Based on corvus_client.py, get_service is /ops/cmdb/{name}.
            # We need a bulk endpoint for the sync script.
            # Let's try /ops/cmdb/all as a guess or check for a list endpoint.
            services_resp = await client.get("/ops/cmdb/all")
            services_resp.raise_for_status()
            services = services_resp.json()
            
            print("Fetching active incidents...")
            incidents_resp = await client.get("/ops/incidents/active")
            incidents_resp.raise_for_status()
            incidents = incidents_resp.json()
            
            print("Fetching active change windows...")
            changes_resp = await client.get("/ops/changes/active")
            changes_resp.raise_for_status()
            changes = changes_resp.json()
            
            # Call the original sync function
            sync(services, incidents, changes)
            print("Sync completed successfully.")
            
        except Exception as e:
            print(f"Sync failed: {e}")
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
