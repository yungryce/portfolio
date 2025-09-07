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

// Name seeds
var namePrefix            = 'portfolio'
var resourceBase          = '${namePrefix}-${suffix}'
var storageAccountName    = toLower('st${resourceBase}')
var logAnalyticsName      = 'law-${resourceBase}'
var appInsightsName       = 'appi-${resourceBase}'
var functionPlanName      = 'fp-${resourceBase}'
var functionAppName       = 'fa-${resourceBase}'
var staticWebAppName      = 'swa-${resourceBase}' // kept for consistency; SWA standard uses global name
var vnetName          = 'vnet-${resourceBase}'
var funcSubnetName    = 'sn-func'
var pepSubnetName     = 'sn-pep'
var kvName            = 'kv-${resourceBase}'
var uamiName          = 'uami-${resourceBase}'
var laName            = 'law-${resourceBase}'
var deploymentContainer   = 'deployment-packages'


// Tag set (extendable later)
var tags = {
  'azd-env-name': suffix
  'owner': namePrefix
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

// ---------- Virtual Network + Subnets ----------
module vnet 'br/public:avm/res/network/virtual-network:0.7.0' = {
  name: 'vnet-${uniqueString(resourceGroup().id,vnetName)}'
  params: {
    name: vnetName
    location: location
    tags: tags
    addressSpacePrefixes: [
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

// ---------- Private DNS Zones ----------
var privateZones = [
  {
    zone: 'privatelink.blob.core.windows.net'
    label: 'blob'
  }
  {
    zone: 'privatelink.queue.core.windows.net'
    label: 'queue'
  }
  {
    zone: 'privatelink.table.core.windows.net'
    label: 'table'
  }
  {
    zone: 'privatelink.vaultcore.azure.net'
    label: 'vault'
  }
]

module dnsZones 'br/public:avm/res/network/private-dns-zone:0.5.0' = [for z in privateZones: {
  name: 'pdns-${uniqueString(resourceGroup().id,z.zone)}'
  params: {
    name: z.zone
    location: 'global'
    tags: tags
    // Link VNet
    virtualNetworkLinks: [
      {
        name: '${vnetName}-link'
        virtualNetworkId: vnet.outputs.resourceId
        registrationEnabled: false
      }
    ]
  }
}]

// Helper map for zone ids
var zoneIds = {
  blob: dnsZones[0].outputs.resourceId
  queue: dnsZones[1].outputs.resourceId
  table: dnsZones[2].outputs.resourceId
  vault: dnsZones[3].outputs.resourceId
}

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
    skuName: 'standard'
  }
}

// ---------- Private Endpoints (Storage + KV) ----------
@description('Private endpoint groups for storage services')
var storagePeGroups = [
  {
    label: 'blob'
    groupIds: [
      'blob'
    ]
    zoneId: zoneIds.blob
  }
  {
    label: 'queue'
    groupIds: [
      'queue'
    ]
    zoneId: zoneIds.queue
  }
  {
    label: 'table'
    groupIds: [
      'table'
    ]
    zoneId: zoneIds.table
  }
]

module peStorage 'br/public:avm/res/network/private-endpoint:0.7.0' = [for s in storagePeGroups: {
  name: 'pe-${uniqueString(resourceGroup().id,storageAccountName)}-${s.label}'
  params: {
    name: 'pep-${storageAccountName}-${s.label}'
    location: location
    tags: tags
    subnetResourceId: '${vnet.outputs.resourceId}/subnets/${pepSubnetName}'
    privateLinkServiceId: storage.outputs.resourceId
    groupIds: s.groupIds
    privateDnsZoneGroup: {
      name: 'default'
      privateDnsZoneConfigs: [
        {
          name: s.label
          privateDnsZoneId: s.zoneId
        }
      ]
    }
  }
}]

module peKeyVault 'br/public:avm/res/network/private-endpoint:0.7.0' = {
  name: 'pe-${uniqueString(resourceGroup().id,kvName)}-vault'
  params: {
    name: 'pep-${kvName}'
    location: location
    tags: tags
    subnetResourceId: '${vnet.outputs.resourceId}/subnets/${pepSubnetName}'
    privateLinkServiceId: keyVault.outputs.resourceId
    groupIds: [
      'vault'
    ]
    privateDnsZoneGroup: {
      name: 'default'
      privateDnsZoneConfigs: [
        {
          name: 'vault'
          privateDnsZoneId: zoneIds.vault
        }
      ]
    }
  }
}

// ---------- App Service Plan (Flex Consumption) ----------
module appServicePlan 'br/public:avm/res/web/serverfarm:0.1.1' = {
  name: 'plan-${uniqueString(resourceGroup().id,functionPlanName)}'
  params: {
    name: functionPlanName
    location: location
    tags: tags
    sku: {
      name: 'FC1'
      tier: 'FlexConsumption'
    }
    reserved: true
    zoneRedundant: zoneRedundant
  }
}

// ---------- Function App (Flex) ----------
module functionApp 'br/public:avm/res/web/site:0.16.0' = {
  name: 'func-${uniqueString(resourceGroup().id,functionAppName)}'
  params: {
    name: functionAppName
    kind: 'functionapp,linux'
    location: location
    tags: union(tags, { 'azd-service-name': 'api' })
    serverFarmResourceId: appServicePlan.outputs.resourceId
    managedIdentities: {
      systemAssigned: true
      userAssignedResourceIds: [
        uami.outputs.resourceId
      ]
    }
    functionAppConfig: {
      deployment: {
        storage: {
          type: 'blobContainer'
          value: '${storage.outputs.primaryBlobEndpoint}${deploymentContainer}'
          authentication: {
            type: 'SystemAssignedIdentity'
          }
        }
      }
      scaleAndConcurrency: {
        maximumInstanceCount: maximumInstanceCount
        instanceMemoryMB: instanceMemoryMB
      }
      runtime: {
        name: functionAppRuntime
        version: functionAppRuntimeVersion
      }
    }
    siteConfig: {
      alwaysOn: false
    }
    configs: [
      {
        name: 'appsettings'
        properties: {
          FUNCTIONS_EXTENSION_VERSION: '~4'
          WEBSITE_RUN_FROM_PACKAGE: string(enableRunFromPackage)
          APPLICATIONINSIGHTS_CONNECTION_STRING: applicationInsights.outputs.connectionString
          APPLICATIONINSIGHTS_AUTHENTICATION_STRING: appInsightsAuthString
          AzureWebJobsStorage__credential: 'managedidentity'
          AzureWebJobsStorage__blobServiceUri: 'https://${storage.outputs.name}.blob.${environment().suffixes.storage}'
          AzureWebJobsStorage__queueServiceUri: 'https://${storage.outputs.name}.queue.${environment().suffixes.storage}'
          AzureWebJobsStorage__tableServiceUri: 'https://${storage.outputs.name}.table.${environment().suffixes.storage}'
        }
      }
    ]
  }
  dependsOn: [
    storage
    applicationInsights
    uami
  ]
}

// ---------- Function VNet Integration (App Service VNet connection) ----------
resource vnetConnection 'Microsoft.Web/sites/virtualNetworkConnections@2023-12-01' = {
  name: '${functionApp.outputs.name}/${vnet.outputs.name}'
  properties: {
    vnetResourceId: vnet.outputs.resourceId
    subnetResourceId: '${vnet.outputs.resourceId}/subnets/${funcSubnetName}'
  }
  dependsOn: [
    functionApp
    vnet
  ]
}

// Function App application settings (separate resource as requested)
resource funcAppSettings 'Microsoft.Web/sites/config@2024-11-01' = {
  name: '${functionApp.name}/appsettings'
  properties: {
    FUNCTIONS_EXTENSION_VERSION: '~4'
    FUNCTIONS_WORKER_RUNTIME: 'python'
    WEBSITE_RUN_FROM_PACKAGE: string(enableRunFromPackage)
    APPLICATIONINSIGHTS_AUTHENTICATION_STRING: appInsightsAuthString
    APPLICATIONINSIGHTS_CONNECTION_STRING: appInsights.properties.ConnectionString
    AzureWebJobsStorage__blobServiceUri: 'https://${saName}.blob.core.windows.net/'
    AzureWebJobsStorage__queueServiceUri: 'https://${saName}.queue.core.windows.net'
    AzureWebJobsStorage__tableServiceUri: 'https://${saName}.table.core.windows.net'
    AzureWebJobsStorage__credential: 'managedidentity'
    AzureWebJobsStorage__ClientId: uami.properties.clientId
    GROQ_API_KEY: '@Microsoft.KeyVault(SecretUri=https://${kvName}.vault.azure.net/secrets/GROQ-API-KEY/)'
    GITHUB_TOKEN: '@Microsoft.KeyVault(SecretUri=https://${kvName}.vault.azure.net/secrets/GITHUB-TOKEN/)'
  }
  dependsOn: [
    functionApp
    keyVault
  ]
}

// ---------------- Static Web App (no AVM module yet) ----------------
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
      apiLocation: ''          // external flex function app
      appLocation: '/'         // root
      outputLocation: 'dist/browser'
    }
  }
}

// ---------- Role Assignments (native) ----------
resource raBlobDataContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid('blobDataContributor', uami.outputs.resourceId, storage.outputs.resourceId)
  scope: storage
  properties: {
    principalId: uami.outputs.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.blobDataContributor)
    principalType: 'ServicePrincipal'
  }
}

resource raQueueDataContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid('queueDataContributor', uami.outputs.resourceId, storage.outputs.resourceId)
  scope: storage
  properties: {
    principalId: uami.outputs.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.queueDataContributor)
    principalType: 'ServicePrincipal'
  }
}

resource raTableDataContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid('tableDataContributor', uami.outputs.resourceId, storage.outputs.resourceId)
  scope: storage
  properties: {
    principalId: uami.outputs.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.tableDataContributor)
    principalType: 'ServicePrincipal'
  }
}

resource raMetricsPublisher 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid('metricsPublisher', uami.outputs.resourceId, logAnalytics.outputs.resourceId)
  scope: logAnalytics
  properties: {
    principalId: uami.outputs.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.metricsPublisher)
    principalType: 'ServicePrincipal'
  }
}

resource raKvSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid('kvSecretsUser', uami.outputs.resourceId, keyVault.outputs.resourceId)
  scope: keyVault
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
