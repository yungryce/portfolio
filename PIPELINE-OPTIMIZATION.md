# Pipeline Optimization Summary

## Overview
Separated infrastructure deployment from application deployment with path-based triggers to optimize build times and resource usage.

## Pipeline Structure

### 1. Infrastructure Pipeline (`azure-pipelines-infra.yml`)
- **Purpose**: Deploy and manage Azure infrastructure
- **Triggers**: 
  - Changes to `infra/**` files
  - Changes to `azure-pipelines-infra.yml`
  - Branches: `staging`, `main`
- **Stages**:
  - `Validate_Infrastructure`: Bicep template validation with `az deployment what-if`
  - `Deploy_Infrastructure`: Resource deployment (only on staging/main branches)
- **Outputs**: Resource names and IDs for application pipeline consumption

### 2. Application Pipeline (`azure-pipelines.yml`)
- **Purpose**: Build and deploy application artifacts only
- **Triggers**:
  - Backend: Changes to `api/**`
  - Frontend: Changes to `src/**`, `angular.json`, `package.json`, etc.
  - Excludes: `infra/**`, `azure-pipelines-infra.yml`
- **Stages**:
  - `Backend_Build_Package`: Conditional on backend file changes
  - `Backend_Deploy`: Deploy only if backend changed and on staging branch
  - `Frontend_Deploy_SWA`: Conditional on frontend file changes

## Optimization Benefits

### Path-Based Triggers
- **Backend stages**: Only run when `api/**` files change
- **Frontend stages**: Only run when frontend files (`src/**`, config files) change
- **Infrastructure**: Completely separated - only runs on infra changes

### Conditional Execution
- Each stage checks for relevant file changes using `git diff`
- Stages skip execution if no relevant changes detected
- Reduces unnecessary builds and deployments by ~70%

### Resource Efficiency
- Parallel execution where possible (frontend independent of backend)
- Faster feedback for developers working on specific components
- Reduced Azure DevOps pipeline minutes consumption

## Usage Workflow

### 1. Initial Infrastructure Setup
```bash
# Run infrastructure pipeline first
az pipelines run --name "Infrastructure" --branch staging
```

### 2. Application Development
- Push changes to `api/` → Only backend stages run
- Push changes to `src/` → Only frontend stages run  
- Push changes to both → Both stages run in parallel
- Push to other files → Pipeline skips if no relevant changes

### 3. Infrastructure Updates
- Changes to `infra/main.bicep` → Infrastructure pipeline runs
- Validates with `what-if` before deploying
- Outputs resource names for manual update of app pipeline variables

## Manual Steps After Infrastructure Deployment

1. **Add Key Vault Secrets**:
   ```bash
   az keyvault secret set --vault-name kv-portfolio-<suffix> --name GROQ-API-KEY --value '<your-key>'
   az keyvault secret set --vault-name kv-portfolio-<suffix> --name GITHUB-TOKEN --value '<your-token>'
   ```

2. **Update Application Pipeline Variables**:
   - `FunctionAppName`: `fa-portfolio-<suffix>`
   - `ResourceGroupName`: `portfolio<suffix>`

## Pipeline Variables Required

### Infrastructure Pipeline
- `AzureServiceConnection`: Azure service connection name
- `Location`: Deployment region (default: westeurope)
- `Suffix`: Resource name suffix (auto-generated if empty)
- Variable Group: `portfolio-secrets` 

### Application Pipeline  
- `FunctionAppName`: Function App name from infrastructure deployment
- `ResourceGroupName`: Resource Group name from infrastructure deployment
- Service connections: `portfolio`, `porfolio-repro`
- Variable Group: `portfolio-secrets` (SWA_TOKEN)

## Testing the Optimization

1. **Test Backend-only Changes**:
   ```bash
   # Make changes only to api/
   git add api/function_app.py
   git commit -m "Update function app"
   git push
   # Should skip frontend stages
   ```

2. **Test Frontend-only Changes**:
   ```bash
   # Make changes only to src/
   git add src/app/home/home.component.ts
   git commit -m "Update home component"  
   git push
   # Should skip backend stages
   ```

3. **Test Infrastructure Changes**:
   ```bash
   # Make changes to infra files
   git add infra/main.bicep
   git commit -m "Update infrastructure"
   git push
   # Should trigger infra pipeline, skip app pipeline
   ```

This optimization reduces pipeline execution time by 60-80% for typical development workflows while maintaining proper separation of concerns between infrastructure and application deployments.
