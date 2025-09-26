@description('Deployment location')
param location string = 'westeurope'

@description('Random suffix for global uniqueness (4-12 chars)')
@minLength(4)
param suffix string

@description('Azure DevOps repo URL (Azure Repos)')
param devOpsRepoUrl string = 'https://dev.azure.com/chxgbx/portfolio/_git/portfolio'

@description('Branch to build/deploy from')
param devOpsBranch string = 'main'

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

// Naming - Centralized and consistent
var namePrefix            = 'portfolio'
var resourceBase          = '${namePrefix}-${suffix}'
var storageAccountName    = toLower('stg${replace(resourceBase, '-', '')}') // use resourceBase but remove '-' for valid
var logAnalyticsName      = 'law-${resourceBase}'
var appInsightsName       = 'appi-${resourceBase}'
var functionPlanName      = 'fp-${resourceBase}'
var functionAppName       = 'fa-${resourceBase}'
var staticWebAppName      = 'swa-${resourceBase}'
var deploymentContainer   = 'deployment-packages'
var vnetName              = 'vnet-${resourceBase}'
var funcSubnetName        = 'sn-func' 
var pepSubnetName         = 'sn-pep'
var kvName                = toLower(substring('kv${resourceBase}${uniqueString(resourceGroup().id, subscription().id)}', 0, 24))
var uamiName              = 'uami-${resourceBase}'

// Tags - consistent across all resources
var tags = {
  'azd-env-name': suffix
  owner: namePrefix
}

// Role Definition IDs
var roleIds = {
  blobDataOwner: 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b'
  storageAccountContributor: '17d1049b-9a84-46fb-8f53-869881c3d3ab' 
  blobDataContributor: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
  queueDataContributor: '974c5e8b-45b9-4653-ba55-5f855dd0fb88'
  tableDataContributor: '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3'
  metricsPublisher: '3913510d-42f4-4e42-8a64-420c390055eb'
  kvSecretsUser: '4633458b-17de-408a-b874-0445c86b69e6'
}

// ---------- Identity (User Assigned) ----------
resource uami 'Microsoft.ManagedIdentity/userAssignedIdentities@2025-01-31-preview' = {
  name: uamiName
  location: location
  tags: tags
}

// ---------- Log Analytics Workspace ----------
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2025-02-01' = {
  name: logAnalyticsName
  location: location
  tags: tags
  properties: {
    retentionInDays: 30
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
      searchVersion: 1
    }
    publicNetworkAccessForIngestion: 'Disabled'
    publicNetworkAccessForQuery: 'Disabled'
    sku: { name: 'PerGB2018' }
  }
}

// ---------- Application Insights (linked to LAW) ----------
resource applicationInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  tags: tags
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
    DisableLocalAuth: true
  }
}

// ---------- Storage Account & Container ----------
resource storage 'Microsoft.Storage/storageAccounts@2025-01-01' = {
  name: storageAccountName
  location: location
  kind: 'StorageV2'
  tags: tags
  sku: { name: 'Standard_LRS' }
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    dnsEndpointType: 'Standard'
    publicNetworkAccess: 'Disabled'
    minimumTlsVersion: 'TLS1_2'
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Deny'
    }
  }
  resource blobServices 'blobServices' = {
    name: 'default'
    properties: {
      deleteRetentionPolicy: {}
    }
    resource storageContainerDeployment 'containers' = {
      name: deploymentContainer
      properties: {
        publicAccess: 'None'
      }
    }
  }
}

// ---------- Virtual Network & Subnets ----------
resource vnet 'Microsoft.Network/virtualNetworks@2024-07-01' = {
  name: vnetName
  location: location
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: [ '10.20.0.0/16' ]
    }
    subnets: [
      {
        name: funcSubnetName
        properties: {
          addressPrefix: '10.20.1.0/24'
          delegations: [
            {
              name: 'functions-delegation'
              properties: {
                serviceName: 'Microsoft.App/environments'
              }
            }
          ]
        }
      }
      {
        name: pepSubnetName
        properties: {
          addressPrefix: '10.20.2.0/24'
          privateEndpointNetworkPolicies: 'Disabled'
        }
      }
    ]
  }
}

// ---------- Private DNS Zones & Links ----------
// Normalize key vault DNS suffix because some environments may return a leading '.' in keyvaultDns or 'vault.'
var privateDnsZoneNames = [
  'privatelink.blob.${environment().suffixes.storage}'
  'privatelink.queue.${environment().suffixes.storage}'
  'privatelink.table.${environment().suffixes.storage}'
]

resource privateDnsZones 'Microsoft.Network/privateDnsZones@2024-06-01' = [for zoneName in privateDnsZoneNames: {
  name: zoneName
  location: 'global'
  tags: tags
}]

// --- Key Vault Private DNS zone (explicit) ---
var keyVaultDnsSuffix = replace(toLower(environment().suffixes.keyvaultDns), 'vault.', '')
var keyVaultPrivateZoneName = 'privatelink.vaultcore.${startsWith(keyVaultDnsSuffix, '.') ? substring(keyVaultDnsSuffix, 1) : keyVaultDnsSuffix}'


resource kvPrivateDnsZone 'Microsoft.Network/privateDnsZones@2024-06-01' = {
  name: keyVaultPrivateZoneName
  location: 'global'
  tags: tags
}
 

resource privateDnsZoneLinks 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = [for (zoneName, i) in privateDnsZoneNames: {
  name: '${zoneName}/${vnetName}-link'
  location: 'global'
  properties: {
    virtualNetwork: { id: vnet.id }
    registrationEnabled: false
  }
  dependsOn: [
    privateDnsZones[i]
  ]
}]

// Explicit KV zone link
resource kvPrivateDnsZoneLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  parent: kvPrivateDnsZone
  name: '${vnetName}-link'
  location: 'global'
  properties: {
    virtualNetwork: { id: vnet.id }
    registrationEnabled: false
  }
}

// ---------- Key Vault ----------
resource keyVault 'Microsoft.KeyVault/vaults@2024-12-01-preview' = {
  name: kvName
  location: location
  tags: tags
  properties: {
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    sku: {
      name: 'standard'
      family: 'A'
    }
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Deny'
    }
    publicNetworkAccess: 'Disabled'
  }
}

// ---------- App Service Plan (Flex Consumption) ----------
resource appServicePlan 'Microsoft.Web/serverfarms@2024-11-01' = {
  name: functionPlanName
  location: location
  kind: 'functionapp,linux'
  tags: tags
  sku: {
    name: 'FC1'
    tier: 'FlexConsumption'
  }
  properties: {
    reserved: true
  }
}

// ---------- Function App ----------
resource functionApp 'Microsoft.Web/sites@2024-11-01' = {
  name: functionAppName
  location: location
  kind: 'functionapp,linux'
  tags: union(tags, { 'azd-service-name': 'api' })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${uami.id}': {}
    }
  }
  properties: {
    serverFarmId: appServicePlan.id
    keyVaultReferenceIdentity: uami.id
    httpsOnly: true
    siteConfig: {
      alwaysOn: false
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
      cors: {
        allowedOrigins: [ 'https://${staticWebAppName}.azurestaticapps.net' ]
        supportCredentials: false
      }
    }
    functionAppConfig: {
      deployment: {
        storage: {
          type: 'blobContainer'
          value: '${storage.properties.primaryEndpoints.blob}${deploymentContainer}'
          authentication: {
            type: 'UserAssignedIdentity'
            userAssignedIdentityResourceId: uami.id
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
  }
}

// ---------- Function App VNet Integration ----------
resource functionAppVnetIntegration 'Microsoft.Web/sites/networkConfig@2024-11-01' = {
  parent: functionApp
  name: 'virtualNetwork'
  properties: {
    subnetResourceId: resourceId('Microsoft.Network/virtualNetworks/subnets', vnetName, funcSubnetName)
    swiftSupported: true
  }
  dependsOn: [
    vnet
  ]
}

// ---------- Private Endpoints ----------
resource peStorageBlob 'Microsoft.Network/privateEndpoints@2024-07-01' = {
  name: 'pe-${storageAccountName}-blob'
  location: location
  tags: tags
  properties: {
    subnet: { id: '${vnet.id}/subnets/${pepSubnetName}' }
    privateLinkServiceConnections: [ {
      name: 'blob'
      properties: {
        privateLinkServiceId: storage.id
        groupIds: [ 'blob' ]
      }
    } ]
  }
}
resource peStorageBlobDns 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-07-01' = {
  parent: peStorageBlob
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [ {
      name: 'blob'
      properties: { privateDnsZoneId: privateDnsZones[0].id }
    } ]
  }
}

resource peStorageQueue 'Microsoft.Network/privateEndpoints@2024-07-01' = {
  name: 'pe-${storageAccountName}-queue'
  location: location
  tags: tags
  properties: {
    subnet: { id: '${vnet.id}/subnets/${pepSubnetName}' }
    privateLinkServiceConnections: [ {
      name: 'queue'
      properties: {
        privateLinkServiceId: storage.id
        groupIds: [ 'queue' ]
      }
    } ]
  }
}
resource peStorageQueueDns 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-07-01' = {
  parent: peStorageQueue
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [ {
      name: 'queue'
      properties: { privateDnsZoneId: privateDnsZones[1].id }
    } ]
  }
}

resource peStorageTable 'Microsoft.Network/privateEndpoints@2024-07-01' = {
  name: 'pe-${storageAccountName}-table'
  location: location
  tags: tags
  properties: {
    subnet: { id: '${vnet.id}/subnets/${pepSubnetName}' }
    privateLinkServiceConnections: [ {
      name: 'table'
      properties: {
        privateLinkServiceId: storage.id
        groupIds: [ 'table' ]
      }
    } ]
  }
}
resource peStorageTableDns 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-07-01' = {
  parent: peStorageTable
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [ {
      name: 'table'
      properties: { privateDnsZoneId: privateDnsZones[2].id }
    } ]
  }
}

resource peKeyVault 'Microsoft.Network/privateEndpoints@2024-07-01' = {
  name: 'pe-${kvName}-vault'
  location: location
  tags: tags
  properties: {
    subnet: { id: '${vnet.id}/subnets/${pepSubnetName}' }
    privateLinkServiceConnections: [ {
      name: 'vault'
      properties: {
        privateLinkServiceId: keyVault.id
        groupIds: [ 'vault' ]
      }
    } ]
  }
}

resource peKeyVaultDns 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-07-01' = {
  parent: peKeyVault
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [ {
      name: 'vault'
      properties: { privateDnsZoneId: kvPrivateDnsZone.id }
    } ]
  }
}

// ---------- Static Web App ----------
resource staticWebApp 'Microsoft.Web/staticSites@2024-11-01' = {
  name: staticWebAppName
  location: location
  tags: tags
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

// Link Static Web App to Function App
resource staticWebAppFunctionLink 'Microsoft.Web/staticSites/linkedBackends@2024-11-01' = {
  parent: staticWebApp
  name: 'backend'
  properties: {
    backendResourceId: functionApp.id
    region: location
  }
}

resource staticWebAppConfig 'Microsoft.Web/staticSites/config@2024-11-01' = {
  parent: staticWebApp
  name: 'appsettings'
  properties: {
    API_BASE_URL: 'https://${functionApp.properties.defaultHostName}/api'
  }
  dependsOn: [ staticWebAppFunctionLink ]
}

// ---------- Role Assignments ----------
// Role assignments scoped at resource group (could refine to resource scope if needed)
resource raBlobDataOwner 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, roleIds.blobDataOwner, uami.name)
  scope: storage
  properties: {
    principalId: uami.properties.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.blobDataOwner)
    principalType: 'ServicePrincipal'
  }
}
resource raStorageAccountContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, roleIds.storageAccountContributor, uami.name)
  scope: storage
  properties: {
    principalId: uami.properties.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.storageAccountContributor)
    principalType: 'ServicePrincipal'
  }
}
resource raBlobDataContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, roleIds.blobDataContributor, uami.name)
  scope: storage
  properties: {
    principalId: uami.properties.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.blobDataContributor)
    principalType: 'ServicePrincipal'
  }
}
resource raQueueDataContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, roleIds.queueDataContributor, uami.name)
  scope: storage
  properties: {
    principalId: uami.properties.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.queueDataContributor)
    principalType: 'ServicePrincipal'
  }
}
resource raTableDataContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, roleIds.tableDataContributor, uami.name)
  scope: storage
  properties: {
    principalId: uami.properties.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.tableDataContributor)
    principalType: 'ServicePrincipal'
  }
}
resource raMetricsPublisher 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(applicationInsights.id, roleIds.metricsPublisher, uami.name)
  scope: applicationInsights
  properties: {
    principalId: uami.properties.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.metricsPublisher)
    principalType: 'ServicePrincipal'
  }
}
resource raKvSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, roleIds.kvSecretsUser, uami.name)
  scope: keyVault
  properties: {
    principalId: uami.properties.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.kvSecretsUser)
    principalType: 'ServicePrincipal'
  }
}

// ---------- Function App Application Settings ----------
// Note: Key Vault references require the Function App to have a managed identity with 'Key Vault
resource functionAppAppSettings 'Microsoft.Web/sites/config@2024-11-01' = {
  parent: functionApp
  name: 'appsettings'
  properties: {
    WEBSITE_VNET_ROUTE_ALL: '1'
    // WEBSITE_CONTENTOVERVNET: '1'
    APPLICATIONINSIGHTS_CONNECTION_STRING: applicationInsights.properties.ConnectionString
    APPLICATIONINSIGHTS_AUTHENTICATION_STRING: appInsightsAuthString
    AzureWebJobsStorage__credential: 'managedidentity'
    AzureWebJobsStorage__blobServiceUri: 'https://${storageAccountName}.blob.${environment().suffixes.storage}'
    AzureWebJobsStorage__queueServiceUri: 'https://${storageAccountName}.queue.${environment().suffixes.storage}'
    AzureWebJobsStorage__tableServiceUri: 'https://${storageAccountName}.table.${environment().suffixes.storage}'
    AzureWebJobsStorage__ClientId: uami.properties.clientId
    GROQ_API_KEY: '@Microsoft.KeyVault(VaultName=${kvName};SecretName=GROQ-API-KEY)'
    GITHUB_TOKEN: '@Microsoft.KeyVault(VaultName=${kvName};SecretName=GITHUB-TOKEN)'
  }
  dependsOn: [
    raKvSecretsUser
    peKeyVault
    peKeyVaultDns
    kvPrivateDnsZoneLink
  ]
}

// ---------- Outputs ----------
output functionAppName string = functionApp.name
output functionAppUrl string = 'https://${functionApp.properties.defaultHostName}'
output staticWebAppName string = staticWebApp.name
output staticWebAppUrl string = 'https://${staticWebApp.properties.defaultHostname}'
output storageAccountName string = storage.name
output applicationInsightsConnectionString string = applicationInsights.properties.ConnectionString
output logAnalyticsWorkspaceId string = logAnalytics.id
output functionAppPrincipalId string = uami.properties.principalId
output resourceGroupName string = resourceGroup().name
output keyVaultName string = keyVault.name
output userAssignedIdentityName string = uami.name
output userAssignedIdentityClientId string = uami.properties.clientId
output groqSecretRef string = '@Microsoft.KeyVault(SecretUri=https://${kvName}.vault.azure.net/secrets/GROQ-API-KEY/)'
output githubTokenRef string = '@Microsoft.KeyVault(SecretUri=https://${kvName}.vault.azure.net/secrets/GITHUB-TOKEN/)'
