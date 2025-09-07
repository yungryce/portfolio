# Infrastructure Deployment

This directory contains the Azure infrastructure-as-code templates for the portfolio project.

## Files Structure

```
infra/
├── main.bicep              # Main Bicep template
├── main.parameters.json    # Example parameters file
└── README.md              # This file
```

## Architecture Overview

The infrastructure creates:

- **Azure Static Web App** (Standard) - Hosts the Angular frontend
- **Azure Functions** (Flex Consumption, Python 3.11) - Backend API
- **Storage Account** (LRS) - For Functions storage
- **Key Vault** (RBAC) - Stores secrets (GROQ_API_KEY, GITHUB_TOKEN)
- **Virtual Network** - With subnets for Functions and Private Endpoints
- **Private Endpoints** - For Storage Account and Key Vault
- **Application Insights** - Monitoring and telemetry
- **User Assigned Managed Identity** - For Functions authentication

## Deployment Process

### Prerequisites

1. Azure CLI installed and authenticated
2. Azure DevOps service connection named `portfolio`
3. Variable group `portfolio-secrets` with:
   - `AppInsightsConnectionString` (get from existing App Insights or leave as placeholder)

### Option 1: Azure DevOps Pipeline (Recommended)

1. Run the `azure-pipelines-infra.yml` pipeline manually
2. The pipeline will generate a random suffix and deploy all resources
3. After deployment, add secrets to Key Vault:

```bash
# Replace <suffix> with the generated suffix from pipeline output
az keyvault secret set --vault-name kv-portfolio-<suffix> --name GROQ-API-KEY --value '<your-groq-key>'
az keyvault secret set --vault-name kv-portfolio-<suffix> --name GITHUB-TOKEN --value '<your-github-token>'
```

4. Update `azure-pipelines.yml` variables with the new resource names:
   - `FunctionAppName`: `fa-portfolio-<suffix>`
   - `ResourceGroupName`: `portfolio<suffix>`

### Option 2: Manual Deployment

1. Generate a random suffix:
   ```bash
   SUFFIX=$(tr -dc a-z0-9 </dev/urandom | head -c 6)
   echo "Using suffix: $SUFFIX"
   ```

2. Create resource group:
   ```bash
   az group create --name "portfolio$SUFFIX" --location westeurope
   ```

3. Deploy template:
   ```bash
   az deployment group create \
     --resource-group "portfolio$SUFFIX" \
     --template-file infra/main.bicep \
     --parameters \
       suffix="$SUFFIX" \
       appInsightsConnectionString="<your-app-insights-connection-string>"
   ```

4. Add secrets to Key Vault (same as above)

## Parameters

| Parameter | Description | Default | Required |
|-----------|-------------|---------|----------|
| `location` | Azure region | `westeurope` | No |
| `suffix` | Unique suffix for resource names | - | Yes |
| `devOpsRepoUrl` | Azure DevOps repo URL | `https://dev.azure.com/chxgbx/portfolio/_git/portfolio` | No |
| `devOpsBranch` | Branch to deploy from | `staging` | No |
| `appInsightsConnectionString` | Application Insights connection string | - | Yes |
| `appInsightsAuthString` | Application Insights auth method | `Authorization=AAD` | No |
| `enablePurgeProtection` | Enable Key Vault purge protection | `false` | No |
| `enableRunFromPackage` | Enable WEBSITE_RUN_FROM_PACKAGE | `true` | No |

## Outputs

After deployment, the template outputs:

- `functionAppName` - Azure Functions app name
- `staticWebAppName` - Static Web App name  
- `keyVaultName` - Key Vault name
- `storageAccountName` - Storage account name
- `userAssignedIdentityName` - Managed Identity name
- `groqSecretRef` - Key Vault reference for GROQ API key
- `githubTokenRef` - Key Vault reference for GitHub token

## Security Configuration

- **Private Endpoints**: Storage Account and Key Vault are only accessible via private endpoints
- **VNet Integration**: Functions app has outbound VNet integration
- **Managed Identity**: Functions uses User Assigned Managed Identity for authentication
- **RBAC**: Key Vault uses Azure RBAC (no access policies)
- **TLS**: All services enforce HTTPS/TLS 1.2+

## Resource Naming Convention

Resources are named with the pattern: `<resource-type>-portfolio-<suffix>`

Examples:
- Function App: `fa-portfolio-abc123`
- Static Web App: `swa-portfolio-abc123`  
- Key Vault: `kv-portfolio-abc123`
- Storage Account: `stportfolioabc123`

## Next Steps After Deployment

1. **Add Key Vault Secrets** (required for Functions to work):
   - `GROQ-API-KEY`: Your Groq API key
   - `GITHUB-TOKEN`: GitHub personal access token

2. **Update CI/CD Pipeline Variables**:
   - Set `FunctionAppName` to the deployed Functions app name
   - Set `ResourceGroupName` to the created resource group name

3. **Configure Static Web App**:
   - The SWA is configured to point to your Azure DevOps repo
   - It will use the existing `azure-pipelines.yml` for builds

4. **Deploy Application Code**:
   - Run the main `azure-pipelines.yml` to build and deploy your application
   - The Functions app is ready to receive deployments
   - The Static Web App will serve your Angular frontend

## Troubleshooting

- **Deployment Fails**: Check if the suffix generates unique global names
- **Functions Can't Access Storage**: Verify managed identity has proper role assignments
- **Key Vault Access Issues**: Ensure RBAC is enabled and managed identity has Key Vault Secrets User role
- **Private Endpoint DNS**: DNS resolution requires the private DNS zones to be properly linked

## Cost Optimization

- Functions uses Flex Consumption (pay-per-use)
- Storage Account uses LRS (lowest cost redundancy)
- Application Insights retention is set to 30 days
- Static Web App Standard tier (required for custom domains and enterprise features)
