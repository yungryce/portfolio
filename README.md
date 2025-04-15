# Portfolio Frontend

A modern Angular-based portfolio site showcasing GitHub projects with advanced features including AI-powered portfolio assistant.

## 🚀 Technology Stack

- **Framework**: Angular 19
- **Styling**: Tailwind CSS 4.0
- **Markdown**: ngx-markdown for rendering project documentation
- **HTTP Client**: Angular's HttpClient for API communication
- **Routing**: Angular Router for SPA navigation
- **State Management**: RxJS Observables

## 📋 Features

- **Dynamic GitHub Integration**: Fetches and displays repository data via GitHub API
- **Portfolio Assistant**: AI-powered assistant to answer questions about portfolio projects
- **Responsive Design**: Mobile-friendly interface with modern UI components
- **Project Showcases**: Detailed views of featured projects with README rendering
- **Caching**: Optimized data fetching with client-side caching
- **Tech Stack Display**: Visual representation of technologies and skills

## 🏗️ Project Structure

- `/src/app/home` - Landing page with personal information and skills overview
- `/src/app/projects` - Project listing and detail views
- `/src/app/portfolio-assistant` - AI assistant interface for portfolio queries
- `/src/app/services` - Shared services for API communication and caching

## 🛠️ Key Components

### Services

- **GitHubService**: Handles communication with GitHub API endpoints
  - Fetches repositories, READMEs, and repository details
  - Transforms raw GitHub data with custom frontend metadata
  - Provides caching for optimized performance

- **PortfolioService**: Manages AI assistant queries
  - Communicates with backend AI processing API
  - Handles response formatting and error states

- **CacheService**: Provides caching functionality
  - In-memory storage for API responses
  - Reduces API calls and improves performance

- **ConfigService**: Manages environment configuration
  - Provides API URLs and environment-specific settings
  - Simplifies environment switching

### Components

- **HomeComponent**: Main landing page showing skills and GitHub stats
- **ProjectsComponent**: Lists featured projects with tech stack visualization
- **ProjectAboutComponent**: Detailed project view with README rendering
- **PortfolioAssistantComponent**: Interface for querying the AI about projects

## 🔄 Data Flow

1. Frontend components request data through services
2. Services check cache before making API calls
3. API responses are cached and transformed for UI rendering
4. Components receive and render the transformed data

## 📦 Build Process

The project uses Angular CLI for building and serving:

```bash
# Development server
npm run start

# Production build
npm run build:prod
```