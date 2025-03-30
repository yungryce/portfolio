const fs = require('fs');
const path = require('path');
require('dotenv').config();

// Get token from env
const githubToken = process.env.GITHUB_TOKEN || '';
console.log(`Updating environment files with token: ${githubToken ? githubToken.substring(0, 4) + '...' : 'no token found'}`);

// Development environment file path
const envDevPath = path.join(__dirname, 'src', 'environments', 'environment.development.ts');

// Read the current file
let envDevContent = fs.readFileSync(envDevPath, 'utf8');

// Replace token value
envDevContent = envDevContent.replace(
  /githubToken:.*?(['"])/,
  `githubToken: '${githubToken}'$1`
);

// Write back
fs.writeFileSync(envDevPath, envDevContent);
console.log(`Updated ${envDevPath} with token from .env`);
