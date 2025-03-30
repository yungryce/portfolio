
    const fs = require('fs');
    const path = require('path');
    
    const envDevPath = path.join(__dirname, 'src', 'environments', 'environment.development.ts');
    
    try {
      console.log('Cleaning up token from environment file...');
      const content = fs.readFileSync(envDevPath, 'utf8');
      const cleanedContent = content.replace(
        /githubToken:\s*['"].*?['"]/, 
        "githubToken: ''"
      );
      fs.writeFileSync(envDevPath, cleanedContent);
      console.log('Token successfully removed from environment file');
    } catch (error) {
      console.error('Error cleaning up token:', error);
    }
  