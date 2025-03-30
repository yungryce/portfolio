// build-config.js
const fs = require('fs');
const path = require('path');

// Output directory
const outputDir = './dist/portfolio/browser';
const configDir = path.join(outputDir, 'assets');

// Ensure the directory exists
if (!fs.existsSync(configDir)) {
  fs.mkdirSync(configDir, { recursive: true });
}

// Try to load token from environment variables first
let githubToken = process.env.GITHUB_TOKEN || '';

// If no environment variable, try to load from local env file
if (!githubToken) {
  try {
    const envPath = path.join(__dirname, 'env');
    if (fs.existsSync(envPath)) {
      const envContent = fs.readFileSync(envPath, 'utf8');
      const envData = JSON.parse(envContent);
      githubToken = envData.githubToken || '';
    }
  } catch (err) {
    console.error('Error reading env file:', err);
  }
}

// Create config.json with the token
const config = { githubToken };
const configPath = path.join(configDir, 'config.json');
fs.writeFileSync(configPath, JSON.stringify(config));

console.log(`Config file generated at: ${configPath}`);