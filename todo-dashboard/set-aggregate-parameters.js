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

// Schedule Pipeline - for generating daily schedule data
const schedulePipeline = [
    // Get only pending todos for scheduling
    { $match: { status: "pending" } },

    // Sort todos by priority first (high priority first)
    // The sort order is opposite from pending todos list because we want high priority first
    {
        $sort: {
            // Convert priority to numeric value for sorting
            // high: 1, medium/initial: 2, low: 3
            $cond: [
                { $eq: ["$priority", "high"] },
                1,
                {
                    $cond: [
                        {
                            $or: [
                                { $eq: ["$priority", "medium"] },
                                { $eq: ["$priority", "initial"] }
                            ]
                        },
                        2,
                        3
                    ]
                }
            ],
            // Then by creation date (newer first)
            created_at: -1
        }
    },

    // Limit to a reasonable number of tasks per day
    { $limit: 8 },

    // Project to add scheduling metadata
    {
        $project: {
            _id: 0,
            todo_id: "$id",
            description: 1,
            priority: 1,
            status: 1,
            created_at: 1,
            // Estimate duration based on priority
            duration_minutes: {
                $cond: [
                    { $eq: ["$priority", "high"] },
                    60, // High priority: 1 hour
                    {
                        $cond: [
                            {
                                $or: [
                                    { $eq: ["$priority", "medium"] },
                                    { $eq: ["$priority", "initial"] }
                                ]
                            },
                            45, // Medium priority: 45 minutes
                            30   // Low priority: 30 minutes
                        ]
                    }
                ]
            }
        }
    }
];

// Construct msg objects for each pipeline
const pendingTodosMsg = {
    mode: 'collection',
    collection: 'todos',
    operation: 'aggregate',
    payload: [pendingTodosPipeline],
    // Add a property to indicate this is for pending todos 
    // so we can identify it in the MongoDB response handler
    _pendingTodos: true
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

// Log what we're requesting
node.warn(`Requesting ${pendingTodosPipeline.length} pending todos`);
node.warn(`Requesting ${completedTodosPipeline.length} completed todos`);
node.warn(`Requesting schedule data with ${schedulePipeline.length} pipeline stages`);

return [
    pendingTodosMsg,
    completedTodosMsg,
    scheduleMsg
];
