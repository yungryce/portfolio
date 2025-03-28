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

// Create config.json with environment variables
const config = {
  githubToken: process.env.GITHUB_TOKEN || ''
};

// Write to output directory
const configPath = path.join(configDir, 'config.json');
fs.writeFileSync(configPath, JSON.stringify(config));
console.log(`Config file generated at: ${configPath}`);