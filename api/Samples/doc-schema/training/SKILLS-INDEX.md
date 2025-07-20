# SKILLS-INDEX.md Template & Agent Instructions

## AGENT USAGE RULES
This template guides generation of comprehensive skills documentation at the REPOSITORY level:
1. Aggregate skills from all containers/projects within the repository
2. Organize skills by competency domains (technical, domain-specific, professional)
3. Reference specific files demonstrating each skill
4. Show skill progression and relationships
5. Use consistent formatting and terminology

## TEMPLATE STRUCTURE

```markdown
# 🎯 Skills & Competencies Index

## 📖 Overview
This document catalogs the comprehensive set of skills and competencies developed across all projects in this repository. It serves as a reference for learners, educators, and professionals to understand the scope and depth of skills acquired.

---

## 🏗️ Core Technical Skills

### {Domain/Category Name} (e.g., Programming Fundamentals)
- **{Skill/Concept}**: {Brief description} | *Demonstrated in: [{file_reference}]*
- **{Skill/Concept}**: {Brief description} | *Demonstrated in: [{file_reference}]*
- **{Skill/Concept}**: {Brief description} | *Demonstrated in: [{file_reference}]*

### {Domain/Category Name} (e.g., Web Development)
- **{Skill/Concept}**: {Brief description} | *Demonstrated in: [{file_reference}]*
- **{Skill/Concept}**: {Brief description} | *Demonstrated in: [{file_reference}]*

### {Domain/Category Name} (e.g., System Administration)
- **{Skill/Concept}**: {Brief description} | *Demonstrated in: [{file_reference}]*
- **{Skill/Concept}**: {Brief description} | *Demonstrated in: [{file_reference}]*

---

## 🔧 Technical Implementation Skills

### {Feature/Component Name} (e.g., API Development)
- **{Skill/Concept}**: *[{file_path}]* – {Description of implementation}
- **{Skill/Concept}**: *[{file_path}]* – {Description of implementation}

### {Feature/Component Name} (e.g., Database Management)
- **{Skill/Concept}**: *[{file_path}]* – {Description of implementation}
- **{Skill/Concept}**: *[{file_path}]* – {Description of implementation}

### {Feature/Component Name} (e.g., Testing & Quality Assurance)
- **{Skill/Concept}**: *[{file_path}]* – {Description of implementation}
- **{Skill/Concept}**: *[{file_path}]* – {Description of implementation}

---

## 📈 Skill Progression Pathway

### Foundation Level
**Prerequisites**: {List basic requirements}
**Core Concepts**: 
- {Fundamental skill/concept}
- {Fundamental skill/concept}
- {Fundamental skill/concept}

### Intermediate Level  
**Builds Upon**: Foundation concepts
**Advanced Concepts**:
- {Intermediate skill/concept}
- {Intermediate skill/concept}
- {Intermediate skill/concept}

### Advanced Level
**Builds Upon**: Intermediate mastery
**Expert Concepts**:
- {Advanced skill/concept}
- {Advanced skill/concept}
- {Advanced skill/concept}

---

## 🌟 Professional & Cross-Cutting Skills

### Code Quality & Standards
- **Style Guidelines**: {e.g., PEP8, Betty, ESLint} | *Files: [{style_config_files}]*
- **Documentation**: Clear code comments and project documentation
- **Version Control**: Git-based source code management and collaboration

### Problem-Solving & Design
- **Algorithm Design**: Systematic approach to solution development
- **Optimization**: Performance and resource usage improvement
- **Architecture**: System design and component interaction

### Testing & Debugging
- **Test Coverage**: Comprehensive test suites | *Tests: [{test_directories}]*
- **Debugging**: Systematic troubleshooting and error resolution
- **Quality Assurance**: Code review and validation processes

---

## 🔗 Container-Specific Skills
*Each container directory contains detailed skills documentation in PROJECT-MANIFEST.md*

| 📂 Container | 🎯 Focus Area | 📝 Key Skills | 📄 Manifest |
|--------------|---------------|----------------|--------------|
| {container_name} | {focus_area} | {key_skills_summary} | [PROJECT-MANIFEST.md]({path}) |
| {container_name} | {focus_area} | {key_skills_summary} | [PROJECT-MANIFEST.md]({path}) |

---

## 📚 References & Resources
- [Repository Architecture](ARCHITECTURE.md)
- [Project Documentation](README.md)
- [{External_Resource_Name}]({url})
- [{External_Resource_Name}]({url})
```

## CONTENT GENERATION GUIDELINES

### Skill Discovery Strategy:
1. **File Analysis**: Examine code files for technology usage patterns
2. **Test Analysis**: Review test files to understand implemented features
3. **Documentation Mining**: Extract skills from existing docs and comments
4. **Project Structure**: Infer skills from directory organization and file types

### Skill Categorization Rules:
- **Core Technical**: Language-specific, framework-specific skills
- **Implementation**: Feature development, integration skills  
- **Professional**: Process, methodology, and quality skills
- **Domain**: Subject-matter expertise (web, systems, data, etc.)

### File Reference Format:
- Use relative paths from repository root
- Link to specific functions/classes when relevant
- Group related files in brackets: *[file1.py, file2.py]*
- Include line numbers for precise references when helpful

### Skill Description Guidelines:
- Be specific and actionable
- Use technical terminology appropriately
- Include practical context/application
- Reference industry standards when applicable

### Progression Mapping:
- Foundation: Basic syntax, concepts, tools
- Intermediate: Feature implementation, integration
- Advanced: Architecture, optimization, leadership

### Quality Standards:
- Every skill MUST have a file reference
- Descriptions should be 1-2 sentences maximum
- Use consistent formatting throughout
- Maintain logical grouping and flow
- Cross-reference with ARCHITECTURE.md and PROJECT-MANIFEST.md files
