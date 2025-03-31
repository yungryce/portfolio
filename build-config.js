const fs = require('fs');
const path = require('path');

console.log('Running build configuration script...');

// Get GitHub token from environment variable
const githubToken = process.env.GITHUB_TOKEN || '';
console.log(`GitHub token available: ${githubToken ? 'Yes' : 'No'}`);

// Create environment.prod.ts file with the token
const prodEnvContent = `export const environment = {
    production: true,
    githubToken: '${githubToken}'
};
`;

const envFilePath = path.join(__dirname, 'src', 'environments', 'environment.prod.ts');
fs.writeFileSync(envFilePath, prodEnvContent);
console.log(`Updated environment.prod.ts with GitHub token: ${githubToken ? 'Present' : 'Missing'}`);

// Also create config.json for runtime fallback
const distPath = path.join(__dirname, 'dist', 'portfolio', 'browser', 'assets');
if (!fs.existsSync(distPath)) {
  console.log(`Creating assets directory: ${distPath}`);
  fs.mkdirSync(distPath, { recursive: true });
}

const configJson = {
  githubToken: githubToken
};

fs.writeFileSync(
  path.join(distPath, 'config.json'),
  JSON.stringify(configJson, null, 2)
);
console.log('Created config.json with GitHub token');