// Get the todo ID from the payload
const todoId = msg.payload.id;

if (!todoId)
{
    return { payload: { status: "error", message: "No todo ID provided" } };
}

// Generate tomorrow's date in YYYY-MM-DD format
const tomorrow = new Date();
tomorrow.setDate(tomorrow.getDate() + 1);
const formattedDate = tomorrow.toISOString().split('T')[0];

// Prepare MongoDB find query
return {
    payload: {
        // Query for MongoDB4 node format
        filter: { id: todoId }
    },
    collection: "todos",
    // Store date in msg so we can use it later
    date: formattedDate
};
