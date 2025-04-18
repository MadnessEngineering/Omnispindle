// Get the todo ID from the payload
const todoId = msg.payload.id;

if (!todoId)
{
    return { payload: { status: "error", message: "No todo ID provided" } };
}

// Prepare MongoDB find query
return {
    payload: {
        // Query for MongoDB4 node format
        filter: { id: todoId }
    },
    collection: "todos"
};
