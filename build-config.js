// build-config.js
const fs = require('fs');
const path = require('path');
const dotenv = require('dotenv');

// Load environment variables from .env
const dotenvResult = dotenv.config();
if (dotenvResult.error) {
  console.error('Error loading .env file:', dotenvResult.error);
} else {
  console.log('.env file loaded successfully');
}

// Output directory
const outputDir = './dist/portfolio/browser';
const configDir = path.join(outputDir, 'assets');

// Ensure the directory exists
if (!fs.existsSync(configDir)) {
  fs.mkdirSync(configDir, { recursive: true });
}

// Load GitHub token from environment variables
const githubToken = process.env.GITHUB_TOKEN || '';

// Log token status (masked)
if (githubToken) {
  const maskedToken = githubToken.substring(0, 4) + '...' + githubToken.substring(githubToken.length - 4);
  console.log(`GitHub token found in environment: ${maskedToken}`);
  
  // Log available environment variables for debugging (without showing the values)
  console.log('Environment variables found:', Object.keys(process.env).filter(key => !key.includes('SECRET') && !key.includes('TOKEN')));
} else {
  console.warn('No GitHub token found in prod environment variables');
  console.log('Available env vars:', Object.keys(process.env).filter(key => !key.includes('SECRET') && !key.includes('TOKEN')));
  
  // Try to directly read from .env file as a backup method
  try {
    const envPath = path.join(__dirname, '.env');
    if (fs.existsSync(envPath)) {
      const envContent = fs.readFileSync(envPath, 'utf8');
      const envLines = envContent.split('\n');
      
      for (const line of envLines) {
        if (line.startsWith('GITHUB_TOKEN=')) {
          const extractedToken = line.substring('GITHUB_TOKEN='.length).trim();
          console.log(`Directly read token from .env file: ${extractedToken.substring(0, 4)}...`);
          // Don't store sensitive data in logs
        }
      }
    }
  } catch (err) {
    console.error('Error directly reading .env file:', err);
  }
}

// Create config.json with the token
const config = { githubToken };
const configPath = path.join(configDir, 'config.json');
fs.writeFileSync(configPath, JSON.stringify(config));

console.log(`Config file generated at: ${configPath}`);

// Update environment.ts with the token
const envFilePath = path.join(__dirname, 'src', 'environments', 'environment.ts');

// Read the current file
let envContent = fs.readFileSync(envFilePath, 'utf8');

// Replace the token placeholder
envContent = envContent.replace(
  /githubToken:\s*['"](.*?)['"]/,
  `githubToken: '${githubToken}'`
);

// Write the updated content back
fs.writeFileSync(envFilePath, envContent);

console.log(`Updated environment file with token: ${githubToken ? 'Token found' : 'No token found'}`);







