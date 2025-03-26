// Placeholder for future schedule pipeline
const schedulePipeline = [];

// Get Pending Todos Pipeline
const pendingTodosPipeline = [
    // Match pending todos
    { $match: { status: "pending" } },

    // Sort by priority (asc) and created date (asc)
    { $sort: { priority: 1, created_at: 1 } }

    // Could add limit stage here if needed
];

// Get Completed Todos Pipeline
const completedTodosPipeline = [
    // Match completed todos
    { $match: { status: "completed" } },

    // Sort by completed date (desc)
    { $sort: { completed_at: -1 } },

    // Limit to last 50
    { $limit: 50 }
];

// Construct msg objects for each pipeline
const pendingTodosMsg = {
    mode: 'collection',
    collection: 'todos',
    operation: 'aggregate',
    payload: [pendingTodosPipeline]
};

const completedTodosMsg = {
    mode: 'collection',
    collection: 'todos',
    operation: 'aggregate',
    payload: [completedTodosPipeline]
};

const scheduleMsg = {
    mode: 'collection',
    collection: 'todos',
    operation: 'aggregate',
    payload: [schedulePipeline]
};

return [
    scheduleMsg,
    pendingTodosMsg,
    completedTodosMsg
];
