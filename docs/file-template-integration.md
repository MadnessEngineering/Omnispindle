# Todomill Projectorium Integration Guide

This guide shows how to integrate the `node-red-contrib-file-template` node with your existing Todomill Projectorium dashboard project.

## Overview

Instead of embedding large HTML templates directly in Node-RED template nodes, you can now:
1. Keep your HTML templates in external files (like `Html/TodoList.html`)
2. Use the file-template node to load and process them
3. Benefit from automatic reloading when files change
4. Maintain better code organization and version control

## Migration Steps

### 1. Install the File Template Node

```bash
cd ~/.node-red
npm install node-red-contrib-file-template
# Restart Node-RED
```

### 2. Replace Template Nodes

Replace your existing template nodes with this pattern:

**Before (embedded template):**
```
[data] → [template node with embedded HTML] → [dashboard]
```

**After (file-based template):**
```
[data] → [file-template node] → [template node] → [dashboard]
```

### 3. Configure File Template Node

1. Drag a `file-template` node from the function category
2. Configure it:
   - **Template File**: `Todomill_projectorium/Html/TodoList.html`
   - **Template Format**: `handlebars` (for variable substitution)
   - **Template Data**: `payload` (or your data field)
   - **Output**: `str` (string output)

### 4. Update Template Syntax (Optional)

If you want to use dynamic data in your templates, add Mustache-style variables:

**Example TodoList.html modifications:**
```html
<!-- Before -->
<h1>Todo Management</h1>

<!-- After -->
<h1>{{title}} Management</h1>
```

## Example Integration Flow

Here's a complete flow showing how to integrate with your todo dashboard:

```json
[
    {
        "id": "todo-data-aggregation",
        "type": "function",
        "name": "Aggregate Todo Data",
        "func": "// Your existing aggregation logic\nmsg.payload = {\n    todos: msg.payload.todos || [],\n    completed: msg.payload.completed || [],\n    total_pending: msg.payload.total_pending || 0,\n    // ... other todo data\n    \n    // Add template variables\n    title: \"Todo\",\n    last_updated: new Date().toISOString()\n};\nreturn msg;",
        "outputs": 1,
        "x": 200,
        "y": 200,
        "wires": [["file-template-todo"]]
    },
    {
        "id": "file-template-todo",
        "type": "file-template",
        "name": "TodoList Template",
        "filename": "Todomill_projectorium/Html/TodoList.html",
        "format": "handlebars",
        "field": "payload",
        "fieldType": "msg",
        "output": "str",
        "x": 400,
        "y": 200,
        "wires": [["dashboard-template"]]
    },
    {
        "id": "dashboard-template",
        "type": "ui_template",
        "name": "Dashboard Display",
        "group": "todo-group",
        "format": "html",
        "storeOutMessages": true,
        "fwdInMessages": true,
        "resendOnRefresh": true,
        "templateScope": "local",
        "x": 600,
        "y": 200,
        "wires": [[]]
    }
]
```

## Benefits of This Approach

### 1. File Organization
- Keep templates in version control as separate files
- Easier to edit with syntax highlighting
- Better organization of large template files

### 2. Development Workflow
- Edit templates in your favorite editor
- Changes automatically reload in Node-RED
- No need to copy/paste between GUI and files

### 3. Template Management
- Share templates between multiple flows
- Easier to maintain and update
- Better code reuse

### 4. Version Control
- Templates are tracked in Git
- Easier to see template changes in diffs
- Better collaboration on template development

## Advanced Usage

### Using with Multiple Templates

You can use different templates for different dashboard sections:

```
[todo-data] → [file-template: TodoList.html] → [dashboard tab 1]
[log-data]  → [file-template: TodoLog.html]  → [dashboard tab 2]
[stats-data] → [file-template: DatabaseStatsDisplay.html] → [dashboard tab 3]
```

### Template Variables for Dynamic Content

Modify your HTML templates to accept dynamic data:

**TodoList.html additions:**
```html
<!-- Add at the top -->
<div class="dynamic-header">
    <h1>{{title || "Todo"}} Management</h1>
    <p>Last updated: {{last_updated}}</p>
    <p>Active filter: {{active_project_filter || "all"}}</p>
</div>

<!-- Use in stats section -->
<div class="stats-item">
    <div class="stats-value">{{custom_stats.high_priority || 0}}</div>
    <div class="stats-label">High Priority ({{priority_threshold || "default"}})</div>
</div>
```

### File Watching in Development

During development, the file-template node will automatically reload your templates when you save changes to the HTML files. This means:

1. Edit `Html/TodoList.html` in your editor
2. Save the file
3. The dashboard updates automatically
4. No need to restart Node-RED or redeploy flows

## Migration Checklist

- [ ] Install `node-red-contrib-file-template` package
- [ ] Identify template nodes to replace
- [ ] Create file-template nodes with correct paths
- [ ] Test that templates load correctly
- [ ] Verify file watching works (edit and save template files)
- [ ] Update any hardcoded values to use template variables
- [ ] Test complete dashboard functionality
- [ ] Update documentation for team members

## Troubleshooting

### Template File Not Found
- Verify the path is relative to Node-RED working directory
- Check file permissions
- Ensure the file exists and is readable

### Variables Not Substituting
- Verify your data structure matches template variables
- Check that you're using correct Mustache syntax: `{{variable}}`
- Use debug nodes to inspect your data structure

### File Watching Not Working
- Restart Node-RED if file watching stops
- Some network file systems may not support watching
- Check Node-RED logs for file watcher errors

## Next Steps

1. Try the integration with one template first (e.g., TodoList.html)
2. Verify it works as expected
3. Gradually migrate other templates
4. Consider adding dynamic variables to enhance your templates
5. Explore using the same templates in multiple contexts

This integration will significantly improve your development workflow while maintaining all the functionality of your current dashboard system. 
