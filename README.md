# Portfolio Project

<p align="center">
  <img src="https://img.shields.io/badge/Angular-17+-red?style=for-the-badge&logo=angular" alt="Angular">
  <img src="https://img.shields.io/badge/Azure-Functions-blue?style=for-the-badge&logo=microsoft-azure" alt="Azure Functions">
  <img src="https://img.shields.io/badge/Status-Production--Ready-green?style=for-the-badge" alt="Status">
</p>

## 📖 Overview

The Portfolio Project is a full-stack application designed to showcase GitHub repositories with AI-powered insights. It features an Angular frontend styled with Tailwind CSS and an Azure Functions backend that integrates GitHub data and AI models. The project provides dynamic repository visualization, AI-driven recommendations, and a seamless user experience.

## 📖 Table of Contents

- [📖 Overview](#-overview)
- [🎯 Features](#-features)
- [🏗️ Architecture](#-architecture)
- [🔧 Technologies](#-technologies)
- [⚙️ Configuration](#️-configuration)
- [🚀 Deployment](#-deployment)
- [💡 Usage](#-usage)
- [📋 Skills Demonstrated](#-skills-demonstrated)
- [🔍 Monitoring](#-monitoring)
- [📄 License](#-license)

---

## 🎯 Features

- **Dynamic Repository Visualization**: Display repositories as cards with key details like title, description, and language usage.
- **AI-Powered Insights**: Generate AI-driven recommendations and insights for repositories.
- **Markdown Rendering**: Render `README.md` files with sanitized Markdown and a linked Table of Contents.
- **Dark/Light Mode**: Toggle between themes with persistent user preferences.
- **Caching**: Optimize performance with in-memory caching for API responses.

## 🏗️ Architecture

- **Frontend**: Angular standalone application (17+) styled with Tailwind CSS.
  - Entry point: `src/main.ts`
  - Routing: `src/app/app.routes.ts`
  - Services: `src/app/services/*`
- **Backend**: Azure Functions (Python) serving GitHub data bundles and AI endpoints.
  - Entry point: `api/function_app.py`
  - Key modules: `api/config/github_repo_manager.py`, `api/ai/repo_scoring_service.py`
- **Integration**: REST API communication between frontend and backend.

## 🔧 Technologies

- **Frontend**: Angular 17+, Tailwind CSS, TypeScript
- **Backend**: Azure Functions, Python 3.11+
- **Libraries**: DOMPurify, Marked.js, RxJS
- **DevOps**: Azure CLI, GitHub Actions

## ⚙️ Configuration

### Environment Variables

| Variable              | Description                          | Example                     |
|-----------------------|--------------------------------------|-----------------------------|
| `AzureWebJobsStorage` | Azure storage connection string      | `DefaultEndpointsProtocol...` |
| `GITHUB_TOKEN`        | GitHub API token                     | `ghp_1234567890abcdef`      |

### Frontend

- Update `src/environments/environment.ts` with the API base URL.

### Backend

- Configure `api/local.settings.json` with the required environment variables.

## 🚀 Deployment

### Frontend

```bash
# Install dependencies
npm install

# Build the application
npm run build

# Start the development server
npm run start
```

### Backend

```bash
# Navigate to the API folder
cd api

# Install dependencies
pip install -r requirements.txt

# Start Azure Functions locally
func start
```

## 💡 Usage

1. Navigate to the Projects page to view repositories as cards.
2. Click on a repository card to view detailed information, including the rendered `README.md`.
3. Use the AI Assistant to query repository insights.
4. Toggle between dark and light themes using the theme switcher.

## 📋 Skills Demonstrated

- **Frontend Development**: Angular, Tailwind CSS, RxJS
- **Backend Development**: Azure Functions, Python
- **AI Integration**: Semantic scoring, AI-driven recommendations
- **Markdown Rendering**: Sanitized Markdown with Table of Contents
- **DevOps**: CI/CD pipelines, Azure resource management

## 🔍 Monitoring

- **Frontend**: Use browser developer tools for debugging.
- **Backend**: Check logs in `api/api_function_app.log` or Azure Portal.

## 📄 License

This project is licensed under the MIT License.