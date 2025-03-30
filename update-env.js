const fs = require('fs');
const path = require('path');
require('dotenv').config();

// Development environment file path
const envDevPath = path.join(__dirname, 'src', 'environments', 'environment.development.ts');
// Lock file to track if we need cleanup
const lockFilePath = path.join(__dirname, '.token-lock');

// Function to inject the token into environment file
function injectToken() {
  // Get token from env
  const githubToken = process.env.GITHUB_TOKEN || '';
  console.log(`Updating environment files with token: ${githubToken ? githubToken.substring(0, 4) + '...' : 'no token found'}`);

  // Read the current file
  let envDevContent = fs.readFileSync(envDevPath, 'utf8');

  // Improved replacement to avoid extra quotes
  envDevContent = envDevContent.replace(
    /githubToken:\s*['"].*?['"]/,
    `githubToken: '${githubToken}'`
  );

  // Write back
  fs.writeFileSync(envDevPath, envDevContent);
  
  // Create a lock file to indicate we need cleanup later
  fs.writeFileSync(lockFilePath, new Date().toISOString());
  
  console.log(`Updated ${envDevPath} with token from .env`);
  console.log(`Created lock file at ${lockFilePath}`);
  
  return githubToken ? true : false;
}

// Function to clean up the token
function cleanupToken() {
  try {
    // Check if lock file exists
    if (!fs.existsSync(lockFilePath)) {
      console.log('No token lock file found, skipping cleanup');
      return;
    }
    
    console.log('Cleaning up token from environment file...');
    
    // Read the file again to get the most recent content
    const content = fs.readFileSync(envDevPath, 'utf8');
    
    // Replace the token with an empty string
    const cleanedContent = content.replace(
      /githubToken:\s*['"].*?['"]/,
      `githubToken: ''`
    );
    
    // Write back the cleaned content
    fs.writeFileSync(envDevPath, cleanedContent);
    
    // Remove the lock file
    fs.unlinkSync(lockFilePath);
    
    console.log('Token removed from environment file');
    console.log('Lock file removed');
  } catch (error) {
    console.error('Error cleaning up token:', error);
  }
}

// Check if we need cleanup (on every run)
function checkAndCleanup() {
  if (fs.existsSync(lockFilePath)) {
    console.log('Found lock file, cleaning up previous token');
    cleanupToken();
  }
}

// Process command line arguments
// Always check for pending cleanup first
checkAndCleanup();

if (process.argv.includes('--cleanup') || process.argv.includes('-c')) {
  // Just clean up if flag is provided
  cleanupToken();
// } else if (process.argv.includes('--inject') || process.argv.includes('-i')) {
//   // Just inject the token
//   injectToken();
} else {
  // Default behavior
  injectToken();
}
