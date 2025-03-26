// Get completed todos from MongoDB
const completedTodos = msg.payload || [];

// Store in global context for other nodes to use
global.set("completedTodos", completedTodos);

// Sort completed todos by completion date (descending)
completedTodos.sort((a, b) => (b.completed_at || 0) - (a.completed_at || 0));

// Limit to most recent for dashboard
const recentCompleted = completedTodos.slice(0, 5);

// Find patterns in similar tasks (simplified implementation)
function findPatterns(todos)
{
    const patterns = [];

    // Group by words in description
    const taskGroups = {};

    todos.forEach(todo =>
    {
        const words = todo.description.toLowerCase().split(/\s+/).filter(w => w.length > 4);

        words.forEach(word =>
        {
            if (!taskGroups[word])
            {
                taskGroups[word] = [];
            }

            // Only add if not already in the group
            if (!taskGroups[word].find(t => t.id === todo.id))
            {
                taskGroups[word].push(todo);
            }
        });
    });

    // Find patterns with at least 2 todos
    Object.keys(taskGroups).forEach(word =>
    {
        if (taskGroups[word].length >= 2)
        {
            patterns.push({
                pattern_id: `pattern-${patterns.length + 1}`,
                keyword: word,
                similar_tasks: taskGroups[word].length,
                template: `${word} task`,
                automation_confidence: Math.round(60 + (taskGroups[word].length * 5)),
                examples: taskGroups[word].slice(0, 3).map(t => t.description)
            });
        }
    });

    return patterns.slice(0, 3); // Return top 3 patterns
}

// Generate simple recommendations
function generateRecommendations(todos)
{
    const recommendations = [];

    // Find pending todos similar to completed todos
    const pendingTodos = global.get("pendingTodos") || [];

    // For demo, just recommend high priority for first few todos
    pendingTodos.slice(0, 2).forEach(todo =>
    {
        if (todo.priority !== "high")
        {
            recommendations.push({
                todo_id: todo.id,
                description: todo.description,
                current_priority: todo.priority || "medium",
                recommended_priority: "high",
                confidence: Math.round(70 + Math.random() * 20)
            });
        }
    });

    return recommendations;
}

// Format AI suggestions for dashboard
const aiSuggestions = {
    automation_suggestions: findPatterns(completedTodos),
    priority_recommendations: generateRecommendations(completedTodos),
    pattern_analysis: {
        total_patterns: completedTodos.length > 0 ? Math.min(3, Math.floor(completedTodos.length / 2)) : 0,
        analyzed_todos: completedTodos.length
    },
    completed: recentCompleted
};

return {
    payload: aiSuggestions,
    topic: "todo/dashboard/suggestions"
};
