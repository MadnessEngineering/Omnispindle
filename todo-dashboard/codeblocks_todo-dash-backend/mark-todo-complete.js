// Get the todo ID from the payload
const todoId = msg.payload.id;

if (!todoId)
{
    return { payload: { status: "error", message: "No todo ID provided" } };
}

// Prepare MongoDB update query for MongoDB4 node
return {
    payload: {
        // Find document by ID
        filter: { id: todoId },
        // Set status to completed and add completed timestamp
        update: {
            $set: {
                status: "completed",
                completed_at: Math.floor(Date.now() / 1000)
            }
        },
        // Additional options
        options: {
            returnNewDocument: true
        }
    },
    collection: "todos"
};
