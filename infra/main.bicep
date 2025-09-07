@description('Deployment location')
param location string = 'westeurope'

@description('Random suffix for global uniqueness (4-12 chars)')
@minLength(4)
param suffix string

@description('Azure DevOps repo URL (Azure Repos)')
param devOpsRepoUrl string = 'https://dev.azure.com/chxgbx/portfolio/_git/portfolio'

@description('Branch to build/deploy from')
param devOpsBranch string = 'feature/infra-test'

@description('Application Insights Authentication String (Authorization=AAD)')
param appInsightsAuthString string = 'Authorization=AAD'

@description('Function App runtime: python | dotnet-isolated | node | java | powerShell')
@allowed(['python','dotnet-isolated','node','java','powerShell'])
param functionAppRuntime string = 'python'

@description('Function App runtime version (Python: 3.11, etc.)')
param functionAppRuntimeVersion string = '3.11'

@description('Flex Consumption max instances')
param maximumInstanceCount int = 100

@description('Flex Consumption instance memory (MB)')
@allowed([512,2048,4096])
param instanceMemoryMB int = 2048

@description('Enable zone redundancy where supported (plan).')
param zoneRedundant bool = false

@description('Toggle WEBSITE_RUN_FROM_PACKAGE setting on Function App.')
param enableRunFromPackage bool = true

// Naming - Centralized and consistent
var namePrefix            = 'portfolio'
var resourceBase          = '${namePrefix}-${suffix}'
var storageAccountName    = toLower('st${replace(resourceBase, '-', '')}') // use resourceBase but remove '-' for valid
var logAnalyticsName      = 'law-${resourceBase}'
var appInsightsName       = 'appi-${resourceBase}'
var functionPlanName      = 'fp-${resourceBase}'
var functionAppName       = 'fa-${resourceBase}'
var staticWebAppName      = 'swa-${resourceBase}'
var deploymentContainer   = 'deployment-packages'
var vnetName              = 'vnet-${resourceBase}'
var funcSubnetName        = 'sn-func'
var pepSubnetName         = 'sn-pep'
var kvName                = 'kv-${resourceBase}'
var uamiName              = 'uami-${resourceBase}'

// Tags
var tags = {
  'azd-env-name': suffix
  owner: namePrefix
}

// Role Definition IDs
var roleIds = {
  blobDataContributor: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
  queueDataContributor: '974c5e8b-45b9-4653-ba55-5f855dd0fb88'
  tableDataContributor: '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3'
  metricsPublisher: '3913510d-42f4-4e42-8a64-420c390055eb'
  kvSecretsUser: '4633458b-17de-408a-b874-0445c86b69e6'
}

// ---------- Identity (User Assigned) ----------
module uami 'br/public:avm/res/managed-identity/user-assigned-identity:0.2.0' = {
  name: 'uami-${uniqueString(resourceGroup().id,uamiName)}'
  params: {
    name: uamiName
    location: location
    tags: tags
  }
}

// ---------- Log Analytics ----------
module logAnalytics 'br/public:avm/res/operational-insights/workspace:0.11.1' = {
  name: 'law-${uniqueString(resourceGroup().id,logAnalyticsName)}'
  params: {
    name: logAnalyticsName
    location: location
    tags: tags
    dataRetention: 30
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
  }
}

// ---------- Application Insights ----------
module applicationInsights 'br/public:avm/res/insights/component:0.6.0' = {
  name: 'appi-${uniqueString(resourceGroup().id,appInsightsName)}'
  params: {
    name: appInsightsName
    location: location
    tags: tags
    workspaceResourceId: logAnalytics.outputs.resourceId
    disableLocalAuth: true
  }
}

// ---------- Storage Account ----------
module storage 'br/public:avm/res/storage/storage-account:0.25.0' = {
  name: 'st-${uniqueString(resourceGroup().id,storageAccountName)}'
  params: {
    name: storageAccountName
    location: location
    tags: tags
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    publicNetworkAccess: 'Disabled'
    dnsEndpointType: 'Standard'
    networkAcls: {
      defaultAction: 'Deny'
      bypass: 'AzureServices'
    }
    minimumTlsVersion: 'TLS1_2'
    blobServices: {
      containers: [
        { name: deploymentContainer }
      ]
    }
    queueServices: {}
    tableServices: {}
  }
}

// ---------- Virtual Network + Subnets (FIX: addressPrefixes) ----------
module vnet 'br/public:avm/res/network/virtual-network:0.7.0' = {
  name: 'vnet-${uniqueString(resourceGroup().id,vnetName)}'
  params: {
    name: vnetName
    location: location
    tags: tags
    addressPrefixes: [
      '10.20.0.0/16'
    ]
    subnets: [
      {
        name: funcSubnetName
        addressPrefixes: [
          '10.20.1.0/24'
        ]
        delegations: [
          {
            name: 'webapp'
            serviceName: 'Microsoft.Web/serverFarms'
          }
        ]
      }
      {
        name: pepSubnetName
        addressPrefixes: [
          '10.20.2.0/24'
        ]
        privateEndpointNetworkPolicies: 'Disabled'
      }
    ]
  }
}

// ---------- Private DNS Zones (unchanged structure) ----------
var privateZones = [
  {
    name: 'privatelink.blob.core.windows.net'
    label: 'blob'
  }
  {
    name: 'privatelink.queue.core.windows.net'
    label: 'queue'
  }
  {
    name: 'privatelink.table.core.windows.net'
    label: 'table'
  }
  {
    name: 'privatelink.vaultcore.azure.net'
    label: 'vault'
  }
]

// Then use a for loop to create the DNS zone modules
module dnsZones 'br/public:avm/res/network/private-dns-zone:0.5.0' = [for (zone, i) in privateZones: {
  name: 'pdns-${uniqueString(resourceGroup().id, zone.name)}'
  params: {
    name: zone.name
    location: 'global'
    tags: tags
    virtualNetworkLinks: [
      {
        name: '${vnetName}-link'
        virtualNetworkId: vnet.outputs.resourceId
        registrationEnabled: false
      }
    ]
  }
}]

// ---------- Key Vault (FIX: sku) ----------
module keyVault 'br/public:avm/res/key-vault/vault:0.12.0' = {
  name: 'kv-${uniqueString(resourceGroup().id,kvName)}'
  params: {
    name: kvName
    location: location
    tags: tags
    enableRbacAuthorization: true
    publicNetworkAccess: 'Disabled'
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Deny'
    }
    sku: {
      name: 'standard'
    }
  }
}

// ---------- Private Endpoints (Explicit; FIX param shape) ----------
// Storage Blob
module peStorageBlob 'br/public:avm/res/network/private-endpoint:0.7.0' = {
  name: 'pe-${uniqueString(resourceGroup().id,'${storageAccountName}-blob')}'
  params: {
    name: 'pep-${storageAccountName}-blob'
    location: location
    tags: tags
    subnetResourceId: '${vnet.outputs.resourceId}/subnets/${pepSubnetName}'
    privateLinkServiceConnections: [
      {
        name: 'blob'
        groupIds: [
          'blob'
        ]
        privateLinkServiceResourceId: storage.outputs.resourceId
      }
    ]
    privateDnsZoneGroupConfigs: [
      {
        name: 'default'
        privateDnsZoneIds: [
          dnsZones[0].outputs.resourceId
        ]
      }
    ]
  }
}
// Storage Queue
module peStorageQueue 'br/public:avm/res/network/private-endpoint:0.7.0' = {
  name: 'pe-${uniqueString(resourceGroup().id,'${storageAccountName}-queue')}'
  params: {
    name: 'pep-${storageAccountName}-queue'
    location: location
    tags: tags
    subnetResourceId: '${vnet.outputs.resourceId}/subnets/${pepSubnetName}'
    privateLinkServiceConnections: [
      {
        name: 'queue'
        groupIds: [
          'queue'
        ]
        privateLinkServiceResourceId: storage.outputs.resourceId
      }
    ]
    privateDnsZoneGroupConfigs: [
      {
        name: 'default'
        privateDnsZoneIds: [
          dnsZones[1].outputs.resourceId
        ]
      }
    ]
  }
}
// Storage Table
module peStorageTable 'br/public:avm/res/network/private-endpoint:0.7.0' = {
  name: 'pe-${uniqueString(resourceGroup().id,'${storageAccountName}-table')}'
  params: {
    name: 'pep-${storageAccountName}-table'
    location: location
    tags: tags
    subnetResourceId: '${vnet.outputs.resourceId}/subnets/${pepSubnetName}'
    privateLinkServiceConnections: [
      {
        name: 'table'
        groupIds: [
          'table'
        ]
        privateLinkServiceResourceId: storage.outputs.resourceId
      }
    ]
    privateDnsZoneGroupConfigs: [
      {
        name: 'default'
        privateDnsZoneIds: [
          dnsZones[2].outputs.resourceId
        ]
      }
    ]
  }
}
// Key Vault
module peKeyVault 'br/public:avm/res/network/private-endpoint:0.7.0' = {
  name: 'pe-${uniqueString(resourceGroup().id,'${kvName}-vault')}'
  params: {
    name: 'pep-${kvName}'
    location: location
    tags: tags
    subnetResourceId: '${vnet.outputs.resourceId}/subnets/${pepSubnetName}'
    privateLinkServiceConnections: [
      {
        name: 'vault'
        groupIds: [
          'vault'
        ]
        privateLinkServiceResourceId: keyVault.outputs.resourceId
      }
    ]
    privateDnsZoneGroupConfigs: [
      {
        name: 'default'
        privateDnsZoneIds: [
          dnsZones[3].outputs.resourceId
        ]
      }
    ]
  }
}

// ---------- Function VNet Integration (FIX name uses compile-time literals) ----------
resource vnetConnection 'Microsoft.Web/sites/virtualNetworkConnections@2023-12-01' = {
  name: '${functionAppName}/${vnetName}'
  properties: {
    vnetResourceId: vnet.outputs.resourceId
    subnetResourceId: '${vnet.outputs.resourceId}/subnets/${funcSubnetName}'
  }
  dependsOn: [
    functionApp
    vnet
  ]
}

// ---------- Static Web App ----------
resource staticWebApp 'Microsoft.Web/staticSites@2024-11-01' = {
  name: staticWebAppName
  location: location
  sku: {
    name: 'Standard'
    tier: 'Standard'
  }
  properties: {
    repositoryUrl: devOpsRepoUrl
    branch: devOpsBranch
    provider: 'AzureDevOps'
    buildProperties: {
      skipGithubActionWorkflowGeneration: true
      apiLocation: ''
      appLocation: '/'
      outputLocation: 'dist/browser'
    }
  }
}

// ---------- Role Assignments ----------
resource raBlobDataContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid('blobDataContributor', uamiName, storageAccountName)
  properties: {
    principalId: uami.outputs.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.blobDataContributor)
    principalType: 'ServicePrincipal'
  }
}

resource raQueueDataContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid('queueDataContributor', uamiName, storageAccountName)
  properties: {
    principalId: uami.outputs.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.queueDataContributor)
    principalType: 'ServicePrincipal'
  }
}

resource raTableDataContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid('tableDataContributor', uamiName, storageAccountName)
  properties: {
    principalId: uami.outputs.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.tableDataContributor)
    principalType: 'ServicePrincipal'
  }
}

resource raMetricsPublisher 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid('metricsPublisher', uamiName, logAnalyticsName)
  properties: {
    principalId: uami.outputs.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.metricsPublisher)
    principalType: 'ServicePrincipal'
  }
}

resource raKvSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid('kvSecretsUser', uamiName, kvName)
  properties: {
    principalId: uami.outputs.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.kvSecretsUser)
    principalType: 'ServicePrincipal'
  }
}

// ---------- Outputs ----------
output functionAppName string = functionApp.outputs.name
output staticWebAppName string = staticWebApp.name
output storageAccountName string = storage.outputs.name
output applicationInsightsConnectionString string = applicationInsights.outputs.connectionString
output logAnalyticsWorkspaceId string = logAnalytics.outputs.resourceId
output functionAppPrincipalId string = functionApp.outputs.systemAssignedMIPrincipalId
output resourceGroupName string = resourceGroup().name
output keyVaultName string = keyVault.outputs.name
output userAssignedIdentityName string = uami.outputs.name
output userAssignedIdentityClientId string = uami.outputs.clientId
output groqSecretRef string = '@Microsoft.KeyVault(SecretUri=https://${kvName}.vault.azure.net/secrets/GROQ-API-KEY/)'
output githubTokenRef string = '@Microsoft.KeyVault(SecretUri=https://${kvName}.vault.azure.net/secrets/GITHUB-TOKEN/)'
