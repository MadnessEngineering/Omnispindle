// Check if we found a todo
if (!msg.payload || msg.payload.length === 0)
{
    return { payload: { status: "error", message: "Todo not found" } };
}

// Get the first todo from the results
const todo = msg.payload[0];

// Check which action we're performing
if (msg.topic === "todo/action/suggestions")
{
    // Create a specific suggestion response for this todo
    const response = {
        todo: {
            id: todo.id,
            description: todo.description,
            current_priority: todo.priority || "medium",
            status: todo.status
        },
        suggestions: {
            suggested_priority: suggestPriority(todo),
            estimated_completion_time: estimateCompletionTime(todo),
            automation_confidence: Math.round(60 + Math.random() * 25)
        }
    };

    return {
        payload: response,
        topic: "todo/dashboard/suggestions"
    };
} else if (msg.topic.includes("schedule"))
{
    // Get the date (either from the msg.date or default to tomorrow)
    const targetDate = msg.date || (() =>
    {
        const tomorrow = new Date();
        tomorrow.setDate(tomorrow.getDate() + 1);
        return tomorrow.toISOString().split('T')[0];
    })();

    // Create a schedule specifically for this todo
    const scheduleResponse = createScheduleForTodo(todo, targetDate);

    return {
        payload: scheduleResponse,
        topic: "todo/dashboard/schedule"
    };
}

// Helper function to suggest priority
function suggestPriority(todo)
{
    // Simple logic - but in real app would be more sophisticated
    const description = todo.description.toLowerCase();

    if (description.includes("urgent") || description.includes("important"))
    {
        return "high";
    }

    if (description.includes("review") || description.includes("meeting"))
    {
        return "medium";
    }

    return todo.priority || "medium";
}

// Helper function to estimate completion time
function estimateCompletionTime(todo)
{
    // Simple logic - but in real app would analyze similar tasks
    const priority = todo.priority || "medium";

    // Estimate in minutes
    const estimates = {
        "high": 90,
        "medium": 60,
        "low": 45,
        "initial": 60
    };

    return estimates[priority];
}

// Create a schedule for a specific todo
function createScheduleForTodo(todo, dateStr)
{
    // Create a Date object from the target date
    const date = new Date(dateStr);
    const weekday = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"][date.getDay()];

    // Define working hours based on the day of the week
    let workingHours;
    const day = date.getDay();

    if (day === 0)
    { // Sunday
        workingHours = { start: "10:00", end: "14:00" };
    } else if (day === 6)
    { // Saturday
        workingHours = { start: "10:00", end: "15:00" };
    } else
    { // Weekday
        workingHours = { start: "09:00", end: "17:00" };
    }

    // Calculate available minutes
    function timeToMinutes(timeStr)
    {
        const [hours, minutes] = timeStr.split(':').map(Number);
        return hours * 60 + minutes;
    }

    function minutesToTime(totalMinutes)
    {
        const hours = Math.floor(totalMinutes / 60);
        const minutes = totalMinutes % 60;
        return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
    }

    const startMinutes = timeToMinutes(workingHours.start);
    const endMinutes = timeToMinutes(workingHours.end);
    const availableMinutes = endMinutes - startMinutes;

    // Duration based on priority
    const durations = {
        "high": 90,
        "medium": 60,
        "low": 45,
        "initial": 60
    };

    const duration = durations[todo.priority || "medium"];

    // Calculate a good time slot based on priority
    let startTimeMinutes;
    if (todo.priority === "high")
    {
        // Schedule high priority in the morning
        startTimeMinutes = startMinutes + 60; // 1 hour after start
    } else if (todo.priority === "low")
    {
        // Schedule low priority in the afternoon
        startTimeMinutes = endMinutes - duration - 60; // 1 hour before end
    } else
    {
        // Schedule medium priority in mid-day
        startTimeMinutes = startMinutes + Math.floor((availableMinutes - duration) / 2);
    }

    // Ensure within bounds
    if (startTimeMinutes < startMinutes)
    {
        startTimeMinutes = startMinutes;
    }
    if (startTimeMinutes + duration > endMinutes)
    {
        startTimeMinutes = endMinutes - duration;
    }

    // Format times
    const startTimeStr = minutesToTime(startTimeMinutes);
    const endTimeStr = minutesToTime(startTimeMinutes + duration);

    // Create the schedule
    return {
        date: dateStr,
        weekday: weekday,
        working_hours: workingHours,
        schedule: [
            {
                todo_id: todo.id,
                description: todo.description,
                priority: todo.priority || "medium",
                start_time: startTimeStr,
                end_time: endTimeStr,
                duration_minutes: duration
            }
        ],
        total_tasks: 1,
        total_scheduled_minutes: duration,
        available_minutes: availableMinutes,
        utilization_percentage: Math.round((duration / availableMinutes) * 100)
    };
}
