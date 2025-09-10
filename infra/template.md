# Infrastructure Requirements for Portfolio Project

This document describes the infrastructure resources, dependencies, and configuration settings as defined in the main deployment template. It is intended as a requirements reference for generating deployment templates in any IaC tool (e.g., Bicep, Terraform).

---

## 1. **Resource Inventory**

### **Identity**
- **User Assigned Managed Identity (UAMI)**
  - Name: `uami-{resourceBase}`
  - Used for authentication by other resources.

### **Monitoring**
- **Log Analytics Workspace**
  - Name: `law-{resourceBase}`
  - Data retention: 30 days
  - Features: Log access using only resource permissions

- **Application Insights**
  - Name: `appi-{resourceBase}`
  - Linked to Log Analytics Workspace
  - Local auth disabled

### **Storage**
- **Storage Account**
  - Name: `st{resourceBase}` (lowercase, no dashes)
  - Public access: Disabled
  - Shared key access: Disabled
  - Public network access: Disabled
  - DNS endpoint type: Standard
  - Network ACLs: Default deny, AzureServices bypass
  - Minimum TLS: 1.2
  - Blob container: `deployment-packages`
  - Queue and Table services enabled

### **Networking**
- **Virtual Network**
  - Name: `vnet-{resourceBase}`
  - Address space: `10.20.0.0/16`
  - Subnets:
    - `sn-func`: `10.20.1.0/24`, delegated to `Microsoft.Web/serverFarms`
    - `sn-pep`: `10.20.2.0/24`, private endpoint network policies disabled

- **Private DNS Zones**
  - For: blob, queue, table, vault (Key Vault)
  - Linked to VNet

### **Key Vault**
- **Azure Key Vault**
  - Name: `kv{resourceBase}{uniqueString(resourceGroup().id)}`
  - RBAC authorization enabled
  - Public network access: Disabled
  - Network ACLs: Default deny, AzureServices bypass
  - SKU: Standard

### **Compute**
- **App Service Plan**
  - Name: `fp-{resourceBase}`
  - SKU: FlexConsumption (FC1)
  - Reserved: true
  - Zone redundant: configurable

- **Function App**
  - Name: `fa-{resourceBase}`
  - Kind: `functionapp,linux`
  - Plan: App Service Plan above
  - Managed identity: UAMI
  - VNet integration: `sn-func` subnet
  - Deployment: Blob container in Storage Account, UAMI authentication
  - Runtime: Python 3.11 (configurable)
  - Scale: max instances and memory configurable
  - Site config: AlwaysOn false, CORS for Static Web App
  - App settings: Application Insights, Key Vault secrets, Storage URIs, UAMI client ID

### **Private Endpoints**
- For Storage (blob, queue, table) and Key Vault
- Each endpoint in `sn-pep` subnet
- Each endpoint has a DNS zone group for the corresponding private DNS zone

### **Static Web App**
- Name: `swa-{resourceBase}`
- SKU: Standard
- Source: Azure DevOps repo and branch
- Build properties: skip GitHub Actions, output path `dist/browser`
- Linked backend: Function App
- App settings: API base URL

### **Role Assignments**
- UAMI is assigned the following roles:
  - Storage Blob Data Owner, Contributor, Queue Data Contributor, Table Data Contributor (on Storage Account)
  - Storage Account Contributor (on Storage Account)
  - Metrics Publisher (on Log Analytics Workspace)
  - Key Vault Secrets User (on Key Vault)

---

## 2. **Resource Dependencies**

- **Application Insights** depends on **Log Analytics Workspace**.
- **Function App** depends on:
  - **App Service Plan**
  - **UAMI**
  - **VNet** (for subnet integration)
  - **Key Vault** (for secrets)
  - **Storage Account** (for deployment package)
- **Private Endpoints** depend on:
  - **VNet** (for subnet)
  - **Storage Account** or **Key Vault** (for service connection)
  - **Private DNS Zones**
- **Private DNS Zones** depend on **VNet**.
- **Role Assignments** depend on the existence of the **UAMI** and the target resource.
- **Static Web App** can be deployed independently but links to the **Function App** as a backend.

---

## 3. **Key Configuration Settings**

- **Naming**: All resources use a consistent `{resourceBase}` pattern for uniqueness and traceability.
- **Security**:
  - All public access is disabled for storage and Key Vault.
  - Network ACLs default to deny, with AzureServices bypass.
  - Managed identities are used for all resource authentication.
- **Networking**:
  - All service endpoints are private, using private endpoints and DNS zones.
  - VNet and subnets are pre-defined and delegated as needed.
- **Observability**:
  - Centralized logging and metrics via Log Analytics and Application Insights.
- **App Integration**:
  - Static Web App is linked to the Function App backend.
  - Function App uses Key Vault for secrets and Storage Account for deployment.
- **Scalability**:
  - Function App plan and scaling parameters are configurable.

---

## 4. **Outputs**

- Names and connection details for all major resources are output for use in downstream pipelines or applications.

---

## 5. **Assumptions**

- All referenced modules output the necessary resource IDs and properties.
- All role assignments are performed at the resource group or resource scope, not at the module scope.
- The deployment is performed in a single resource group and region.

---

**This requirements file can be used as a reference for generating equivalent infrastructure code in Bicep, Terraform, or