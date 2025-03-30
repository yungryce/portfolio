// build-config.js
const fs = require('fs');
const path = require('path');

// Output directory from Azure SWA config
const outputDir = './dist/portfolio/browser';
const configDir = path.join(outputDir, 'assets');

// Ensure the directory exists
if (!fs.existsSync(configDir)) {
  fs.mkdirSync(configDir, { recursive: true });
}

// Try to load token from environment variables first, then from the local env file
let githubToken = process.env.GH_PAT || process.env.GITHUB_TOKEN || '';

if (!githubToken) {
  const envPath = path.join(__dirname, 'env');
  if (fs.existsSync(envPath)) {
    try {
      const envContent = fs.readFileSync(envPath, 'utf8');
      const envJson = JSON.parse(envContent);
      githubToken = envJson.githubToken || '';
    } catch (err) {
      console.error('Error reading local env file:', err);
    }
  }
}

// Create config.json with the githubToken
const config = { githubToken };
const configPath = path.join(configDir, 'config.json');
fs.writeFileSync(configPath, JSON.stringify(config));
console.log(`Config file generated at: ${configPath}`);