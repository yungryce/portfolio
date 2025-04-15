# Frontend Project Manifest

## 🎯 Purpose
The frontend module provides a responsive user interface for the portfolio website, showcasing projects and enabling AI-powered queries about the portfolio.

## 📂 Structure
- **app/** - Angular application components and services
  - **home/** - Landing page with skills overview
  - **projects/** - Project listing and detailed views
  - **portfolio-assistant/** - AI assistant interface
  - **services/** - API communication and data management

## 🧩 Key Components

### Core Components
- **HomeComponent**: Displays personal information and skills overview
- **ProjectsComponent**: Lists featured GitHub repositories with custom metadata
- **ProjectAboutComponent**: Shows detailed project information including README
- **PortfolioAssistantComponent**: Interface for querying the AI assistant

### Services
- **GitHubService**: Handles communication with GitHub API via backend proxy
- **PortfolioService**: Manages AI assistant query processing
- **CacheService**: Provides in-memory caching for API responses
- **ConfigService**: Manages environment configuration

## 🔄 Workflows

### Project Display Workflow
1. ProjectsComponent requests featured repositories from GitHubService
2. GitHubService fetches data from backend API
3. ProjectsComponent renders repository cards with custom styling
4. User interactions trigger detailed views with README content

### AI Assistant Workflow
1. User submits query through PortfolioAssistantComponent
2. PortfolioService sends query to backend API
3. Response is processed and displayed as formatted markdown
4. Error states are handled with user-friendly messages

## 💪 Technical Highlights
- Responsive design using Tailwind CSS
- Type-safe API communication with TypeScript interfaces
- Modular component architecture with standalone components
- Optimized performance through client-side caching
- Markdown rendering for README and AI responses

## 📚 Dependencies
- Angular 19 framework
- Tailwind CSS 4.0 for styling
- ngx-markdown for content rendering
- RxJS for reactive programming patterns