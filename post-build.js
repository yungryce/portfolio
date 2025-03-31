const fs = require('fs');
const path = require('path');

console.log('Running post-build configuration...');

// Get GitHub token from environment variable
const githubToken = process.env.GITHUB_TOKEN || '';
console.log(`GitHub token available for runtime config: ${githubToken ? 'Yes' : 'No'}`);

// Create assets directory if it doesn't exist
const assetsPath = path.join(__dirname, 'dist', 'portfolio', 'browser', 'assets');
if (!fs.existsSync(assetsPath)) {
  console.log(`Creating assets directory: ${assetsPath}`);
  fs.mkdirSync(assetsPath, { recursive: true });
}

// Create runtime config.json
const configJson = {
  githubToken: githubToken
};

fs.writeFileSync(
  path.join(assetsPath, 'config.json'),
  JSON.stringify(configJson, null, 2)
);
console.log('Created runtime config.json with GitHub token');