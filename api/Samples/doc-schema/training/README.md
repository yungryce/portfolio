# README.md Template & Agent Instructions

## AGENT USAGE RULES
When generating README.md files, follow this template structure EXACTLY:
1. Extract project information from existing files and code
2. Maintain professional formatting with badges and visual elements
3. Create comprehensive but concise content
4. Include all required sections listed below
5. Use consistent markdown formatting across all generated READMEs

## TEMPLATE STRUCTURE

```markdown
<p align="center">
  <img src="https://img.shields.io/badge/{TECH_STACK}-{VERSION}-{COLOR}" alt="{PROJECT_NAME}">
  <img src="https://img.shields.io/badge/Status-{STATUS}-{COLOR}" alt="Status">
</p>

<div align="center">
  <h1>🚀 {PROJECT_NAME}</h1>
  <p><em>{PROJECT_SUBTITLE/DESCRIPTION}</em></p>
</div>

---

## 📋 Table of Contents
- [📖 Overview](#-overview)
- [🎯 Learning Objectives](#-learning-objectives)
- [🛠️ Tech Stack](#️-tech-stack)
- [📁 Project Structure](#-project-structure)
- [🚀 Getting Started](#-getting-started)
- [💡 Usage](#-usage)
- [🏆 Key Features](#-key-features)
- [📚 Resources](#-resources)
- [👥 Contributors](#-contributors)

## 📖 Overview
{Comprehensive project description - extract from existing files or infer from code structure}

## 🎯 Learning Objectives
{List key learning outcomes - derive from SKILLS-INDEX.md or PROJECT-MANIFEST.md when available}

## 🛠️ Tech Stack
{Technology details - analyze file extensions, imports, and dependencies}

**Core Technologies:**
- {Primary language/framework}
- {Secondary technologies}

**Development Tools:**
- {Build tools, testing frameworks, etc.}

## 📁 Project Structure
{Generate directory tree showing key files and folders}

## 🚀 Getting Started

### Prerequisites
{List system requirements and dependencies}

### Installation
{Step-by-step setup instructions}

### Running the Project
{Execution commands and procedures}

## 💡 Usage
{Examples and use cases}

## 🏆 Key Features
{Major functionalities and capabilities}

## 📚 Resources
{Links to documentation, tutorials, or related materials}

## 👥 Contributors
{Author information from AUTHORS file when available}
```

## CONTENT GENERATION GUIDELINES

### Dynamic Content Extraction:
- **Project Name**: Use directory name or extract from existing README
- **Tech Stack**: Analyze file extensions (.py, .js, .c, etc.)
- **Description**: Extract from existing documentation or infer from project purpose
- **Features**: Identify from file structure and code analysis
- **Prerequisites**: Determine from requirements files, Makefiles, or package.json

### Badge Generation Rules:
- Language badges: Use primary programming language
- Status badges: "Active", "Completed", "In Progress"
- Version badges: Extract from version files or package managers

### Section Requirements:
- **Overview**: Must be comprehensive yet concise (2-3 paragraphs)
- **Learning Objectives**: Minimum 3 objectives, maximum 8
- **Tech Stack**: Separate core vs development tools
- **Project Structure**: Show logical organization, not every file
- **Getting Started**: Must include Prerequisites, Installation, Running steps

### Quality Standards:
- Professional language and formatting
- Consistent emoji usage for section headers
- Proper markdown syntax
- Logical flow and organization
- Links to relevant files and resources

### Cross-Reference Integration:
- Link to SKILLS-INDEX.md for detailed skills
- Reference ARCHITECTURE.md for technical details
- Include PROJECT-MANIFEST.md information for containers
- Connect to related projects when applicable
