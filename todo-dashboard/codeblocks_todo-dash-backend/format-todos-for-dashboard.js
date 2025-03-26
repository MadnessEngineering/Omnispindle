// Get all the todos
const todos = msg.payload || [];

// Count priorities
const highPriority = todos.filter(todo => todo.priority === "high").length;
const mediumPriority = todos.filter(todo => todo.priority === "medium" || todo.priority === "initial").length;
const lowPriority = todos.filter(todo => todo.priority === "low").length;

// Sort pending todos by priority and creation date
const priorityRank = { "high": 0, "medium": 1, "low": 2, "initial": 1 };
todos.sort((a, b) =>
{
    // First by priority
    const priorityDiff = priorityRank[a.priority || "medium"] - priorityRank[b.priority || "medium"];
    if (priorityDiff !== 0) return priorityDiff;

    // Then by creation date (descending)
    return (b.created_at || 0) - (a.created_at || 0);
});

// Store completed todos in flow context for AI Pattern Analysis
const completedTodos = global.get("completedTodos") || [];

// Format for dashboard
const dashboardData = {
    todos: todos,
    total_pending: todos.length,
    total_completed: completedTodos.length,
    high_priority: highPriority,
    medium_priority: mediumPriority,
    low_priority: lowPriority,
    last_updated: new Date().toISOString()
};

return {
    payload: dashboardData,
    topic: "todo/dashboard/todos"
};
