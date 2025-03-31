(function(window) {
  window.__env = window.__env || {};
  
  // Make a runtime attempt to expose environment variables
  console.log('Initializing runtime environment variables');
  
  // If running in Azure Static Web Apps, environment variables 
  // should be available through window.__env
  try {
    if (window.GITHUB_TOKEN) {
      window.__env.GITHUB_TOKEN = window.GITHUB_TOKEN;
      console.log('Found GITHUB_TOKEN in window');
    }
  } catch (error) {
    console.error('Error setting up runtime environment:', error);
  }
})(this);