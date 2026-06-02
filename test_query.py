from copado_hx.api.base import SalesforceClient
from copado_hx.utils.config import get_settings
from copado_hx.auth.store import get_token

s = get_settings()
c = SalesforceClient(s.sf_instance_url, get_token('sf_access_token'))

# Query for objects with "commit" in the name
r = c.tooling_query("SELECT QualifiedApiName FROM EntityDefinition WHERE QualifiedApiName LIKE '%commit%' ORDER BY QualifiedApiName")
print(f'Found {len(r)} objects with "commit" in name:')
for x in r:
    print(f"  {x.get('QualifiedApiName')}")
