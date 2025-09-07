@description('Deployment location')
param location string = 'westeurope'

@description('Random suffix for global uniqueness (4-12 chars)')
@minLength(4)
param suffix string

@description('Azure DevOps repo URL (Azure Repos)')
param devOpsRepoUrl string = 'https://dev.azure.com/chxgbx/portfolio/_git/portfolio'

@description('Branch to build/deploy from')
param devOpsBranch string = 'staging'

@description('Application Insights Authentication String (Authorization=AAD)')
param appInsightsAuthString string = 'Authorization=AAD'

@description('Enable purge protection on Key Vault')
param enablePurgeProtection bool = false

@description('Toggle WEBSITE_RUN_FROM_PACKAGE setting')
param enableRunFromPackage bool = true

// Name seeds
var namePrefix        = 'portfolio'
var vnetName          = 'vnet-${namePrefix}-${suffix}'
var funcSubnetName    = 'sn-func'
var pepSubnetName     = 'sn-pep'
var saName            = toLower('st${namePrefix}${suffix}')
var kvName            = 'kv-${namePrefix}-${suffix}'
var uamiName          = 'uami-${namePrefix}-${suffix}'
var planName          = 'fp-${namePrefix}-${suffix}'
var funcName          = 'fa-${namePrefix}-${suffix}'
var swaName           = 'swa-${namePrefix}-${suffix}'
var laName            = 'law-${namePrefix}-${suffix}'
var appInsightsName   = 'appi-${namePrefix}-${suffix}'

// Role Definition IDs
var roleIds = {
  blobDataContributor: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
  queueDataContributor: '974c5e8b-45b9-4653-ba55-5f855dd0fb88'
  tableDataContributor: '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3'
  metricsPublisher: '3913510d-42f4-4e42-8a64-420c390055eb'
  kvSecretsUser: '4633458b-17de-408a-b874-0445c86b69e6'
}

resource uami 'Microsoft.ManagedIdentity/userAssignedIdentities@2025-01-31-preview' = {
  name: uamiName
  location: location
}

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2025-02-01' = {
  name: laName
  location: location
  properties: {
    retentionInDays: 30
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
  }
  sku: {
    name: 'PerGB2018'
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    Flow_Type: 'Bluefield'
    WorkspaceResourceId: logAnalytics.id
  }
}

resource storage 'Microsoft.Storage/storageAccounts@2025-01-01' = {
  name: saName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Deny'
    }
    supportsHttpsTrafficOnly: true
  }
}

resource vnet 'Microsoft.Network/virtualNetworks@2024-07-01' = {
  name: vnetName
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: [
        '10.20.0.0/16'
      ]
    }
    subnets: [
      {
        name: funcSubnetName
        properties: {
          addressPrefix: '10.20.1.0/24'
          delegations: [
            {
              name: 'webapp'
              properties: {
                serviceName: 'Microsoft.Web/serverFarms'
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

resource keyVault 'Microsoft.KeyVault/vaults@2024-12-01-preview' = {
  name: kvName
  location: location
  properties: {
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    sku: {
      family: 'A'
      name: 'standard'
    }
    enablePurgeProtection: enablePurgeProtection
    enabledForTemplateDeployment: true
    publicNetworkAccess: 'Disabled'
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Deny'
    }
  }
}

resource privateDnsBlob 'Microsoft.Network/privateDnsZones@2024-06-01' = {
  name: 'privatelink.blob.core.windows.net'
  location: 'global'
}

resource privateDnsQueue 'Microsoft.Network/privateDnsZones@2024-06-01' = {
  name: 'privatelink.queue.core.windows.net'
  location: 'global'
}

resource privateDnsTable 'Microsoft.Network/privateDnsZones@2024-06-01' = {
  name: 'privatelink.table.core.windows.net'
  location: 'global'
}

resource privateDnsVault 'Microsoft.Network/privateDnsZones@2024-06-01' = {
  name: 'privatelink.vaultcore.azure.net'
  location: 'global'
}

resource vnetLinkBlob 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  name: '${vnet.name}-link'
  parent: privateDnsBlob
  location: 'global'
  properties: {
    virtualNetwork: {
      id: vnet.id
    }
    registrationEnabled: false
  }
}

resource vnetLinkQueue 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  name: '${vnet.name}-link'
  parent: privateDnsQueue
  location: 'global'
  properties: {
    virtualNetwork: {
      id: vnet.id
    }
    registrationEnabled: false
  }
}

resource vnetLinkTable 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  name: '${vnet.name}-link' 
  parent: privateDnsTable
  location: 'global'
  properties: {
    virtualNetwork: {
      id: vnet.id
    }
    registrationEnabled: false
  }
}

resource vnetLinkVault 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  name: '${vnet.name}-link' 
  parent: privateDnsVault
  location: 'global'
  properties: {
    virtualNetwork: {
      id: vnet.id
    }
    registrationEnabled: false
  }
}

// Private Endpoints (blob, queue, table)
resource pepBlob 'Microsoft.Network/privateEndpoints@2024-07-01' = {
  name: 'pep-${saName}-blob'
  location: location
  properties: {
    subnet: {
      id: '${vnet.id}/subnets/${pepSubnetName}'
    }
    privateLinkServiceConnections: [
      {
        name: 'blob'
        properties: {
          privateLinkServiceId: storage.id
          groupIds: [
            'blob'
          ]
        }
      }
    ]
    customDnsConfigs: []
  }
  dependsOn: [
    storage
    vnet
  ]
}

resource pepQueue 'Microsoft.Network/privateEndpoints@2024-07-01' = {
  name: 'pep-${saName}-queue'
  location: location
  properties: {
    subnet: {
      id: '${vnet.id}/subnets/${pepSubnetName}'
    }
    privateLinkServiceConnections: [
      {
        name: 'queue'
        properties: {
          privateLinkServiceId: storage.id
          groupIds: [
            'queue'
          ]
        }
      }
    ]
  }
}

resource pepTable 'Microsoft.Network/privateEndpoints@2024-07-01' = {
  name: 'pep-${saName}-table'
  location: location
  properties: {
    subnet: {
      id: '${vnet.id}/subnets/${pepSubnetName}'
    }
    privateLinkServiceConnections: [
      {
        name: 'table'
        properties: {
          privateLinkServiceId: storage.id
          groupIds: [
            'table'
          ]
        }
      }
    ]
  }
}

// Key Vault Private Endpoint
resource pepKv 'Microsoft.Network/privateEndpoints@2024-07-01' = {
  name: 'pep-${kvName}'
  location: location
  properties: {
    subnet: {
      id: '${vnet.id}/subnets/${pepSubnetName}'
    }
    privateLinkServiceConnections: [
      {
        name: 'vault'
        properties: {
          privateLinkServiceId: keyVault.id
          groupIds: [
            'vault'
          ]
        }
      }
    ]
  }
}

// Function Flex Consumption Plan (preview)
resource funcPlan 'Microsoft.Web/serverfarms@2024-11-01' = {
  name: planName
  location: location
  sku: {
    name: 'FC1'
    tier: 'FlexConsumption'
  }
  properties: {
    reserved: true
  }
}

resource functionApp 'Microsoft.Web/sites@2024-11-01' = {
  name: funcName
  location: location
  kind: 'functionapp,linux'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${uami.id}': {}
    }
  }
  properties: {
    httpsOnly: true
    serverFarmId: funcPlan.id
    siteConfig: {
      linuxFxVersion: 'Python|3.11'
      appSettings: [
        // Minimal until dedicated appsettings resource below
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
      ]
      ftpsState: 'Disabled'
    }
    functionAppConfig: {
      deployment: {
        storage: {
          type: 'blobContainer'
          value: 'https://${saName}.blob.core.windows.net/deployment-packages'
          authentication: {
            type: 'UserAssignedIdentity'
            userAssignedIdentityResourceId: uami.id
          }
        }
      }
      scaleAndConcurrency: {
        maximumInstanceCount: 100
        instanceMemoryMB: 2048
      }
      runtime: {
        name: 'python'
        version: '3.11'
      }
    }
  }
  dependsOn: [
    funcPlan
    uami
  ]
}

// Outbound VNet integration (Web Apps connection) - preview resource
resource vnetConnection 'Microsoft.Web/sites/virtualNetworkConnections@2023-12-01' = {
  name: '${functionApp.name}/${vnet.name}'
  properties: {
    vnetResourceId: vnet.id
    subnetResourceId: '${vnet.id}/subnets/${funcSubnetName}'
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

// Static Web App (Standard)
resource staticWebApp 'Microsoft.Web/staticSites@2024-11-01' = {
  name: swaName
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
      apiLocation: '' // external Function App
      appLocation: '/'
      outputLocation: 'dist/browser'
    }
  }
}

// Role Assignments
resource raBlobDataContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid('blobDataContributor', uami.id, storage.id)
  scope: storage
  properties: {
    principalId: uami.properties.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.blobDataContributor)
    principalType: 'ServicePrincipal'
  }
}

resource raQueueDataContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid('queueDataContributor', uami.id, storage.id)
  scope: storage
  properties: {
    principalId: uami.properties.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.queueDataContributor)
    principalType: 'ServicePrincipal'
  }
}

resource raTableDataContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid('tableDataContributor', uami.id, storage.id)
  scope: storage
  properties: {
    principalId: uami.properties.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.tableDataContributor)
    principalType: 'ServicePrincipal'
  }
}

resource raMetricsPublisher 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid('metricsPublisher', uami.id, logAnalytics.id)
  scope: logAnalytics
  properties: {
    principalId: uami.properties.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.metricsPublisher)
    principalType: 'ServicePrincipal'
  }
}

resource raKvSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid('kvSecretsUser', uami.id, keyVault.id)
  scope: keyVault
  properties: {
    principalId: uami.properties.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.kvSecretsUser)
    principalType: 'ServicePrincipal'
  }
}

// DNS Zone Groups for Private Endpoints (required for proper DNS resolution)
resource pepBlobDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-07-01' = {
  name: '${pepBlob.name}/default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'blob'
        properties: {
          privateDnsZoneId: privateDnsBlob.id
        }
      }
    ]
  }
}

resource pepQueueDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-07-01' = {
  name: '${pepQueue.name}/default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'queue'
        properties: {
          privateDnsZoneId: privateDnsQueue.id
        }
      }
    ]
  }
}

resource pepTableDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-07-01' = {
  name: '${pepTable.name}/default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'table'
        properties: {
          privateDnsZoneId: privateDnsTable.id
        }
      }
    ]
  }
}

resource pepKvDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-07-01' = {
  name: '${pepKv.name}/default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'vault'
        properties: {
          privateDnsZoneId: privateDnsVault.id
        }
      }
    ]
  }
}

output resourceGroupName string = resourceGroup().name
output functionAppName string = functionApp.name
output staticWebAppName string = staticWebApp.name
output keyVaultName string = keyVault.name
output storageAccountName string = storage.name
output userAssignedIdentityName string = uami.name
output userAssignedIdentityClientId string = uami.properties.clientId
output groqSecretRef string = '@Microsoft.KeyVault(SecretUri=https://${kvName}.vault.azure.net/secrets/GROQ-API-KEY/)'
output githubTokenRef string = '@Microsoft.KeyVault(SecretUri=https://${kvName}.vault.azure.net/secrets/GITHUB-TOKEN/)'
output applicationInsightsConnectionString string = appInsights.properties.ConnectionString
