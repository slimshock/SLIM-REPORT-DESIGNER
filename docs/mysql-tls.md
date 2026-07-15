# MySQL TLS Configuration

The current public connection model does not persist TLS certificate paths. Deployments requiring
TLS should supply a policy-controlled provider/connection factory that passes driver TLS arguments
from application configuration, not report JSON.

Require certificate verification in production, keep CA/client material outside templates and web
roots, use absolute application-controlled paths, and reject user-provided TLS options. Validate TLS
at startup and include only a boolean verification state in protected diagnostics. Do not weaken
hostname or certificate checks to make a development server connect.
