// Get the date from the payload
const targetDate = msg.payload.date;

// Create a Date object from the target date
const date = new Date(targetDate);
const weekday = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"][date.getDay()];

// Define working hours based on the day of the week
let workingHours;
const day = date.getDay(); // 0 = Sunday, 1 = Monday, ...

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

const startMinutes = timeToMinutes(workingHours.start);
const endMinutes = timeToMinutes(workingHours.end);
const availableMinutes = endMinutes - startMinutes;

// Get todos from context
let pendingTodos = [];

// Try to get pending todos from flow context
const flowContext = flow.get('pendingTodos');
if (flowContext && Array.isArray(flowContext))
{
    pendingTodos = flowContext;
}

// If no todos in context, try to get them from MongoDB
if (pendingTodos.length === 0)
{
    // This is just a placeholder. We'll make a real MongoDB query for todos in the MongoDB flow
    // In a real implementation, we would query MongoDB here
    // For now we'll use some example todos
    pendingTodos = [
        { id: "123", description: "Review project proposal", priority: "high" },
        { id: "456", description: "Team meeting", priority: "medium" },
        { id: "789", description: "Update documentation", priority: "low" }
    ];
}

// Function to generate time string from minutes
function minutesToTime(totalMinutes)
{
    const hours = Math.floor(totalMinutes / 60);
    const minutes = totalMinutes % 60;
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
}

// Generate schedule from todos
function generateSchedule(todos, startTime, availableMins)
{
    // Sort by priority
    const priorityRank = { "high": 0, "medium": 1, "low": 2, "initial": 1 };
    todos.sort((a, b) =>
    {
        return priorityRank[a.priority || "medium"] - priorityRank[b.priority || "medium"];
    });

    // Define task durations based on priority
    const durations = {
        "high": 90, // 1.5 hours
        "medium": 60, // 1 hour
        "low": 45, // 45 minutes
        "initial": 60 // 1 hour
    };

    const schedule = [];
    let currentTime = startTime;
    let scheduledMinutes = 0;

    // Schedule high priority tasks first, then medium, then low
    todos.slice(0, 5).forEach((todo, index) =>
    {
        // Calculate duration
        const duration = durations[todo.priority || "medium"];

        // Check if we have enough time left (including break)
        const breakTime = index > 0 ? 15 : 0;
        if (scheduledMinutes + duration + breakTime > availableMins)
        {
            return; // Skip if not enough time
        }

        // Add break time if not the first task
        if (index > 0)
        {
            currentTime += 15;
            scheduledMinutes += 15;
        }

        // Calculate start and end times
        const startTimeStr = minutesToTime(currentTime);
        const endTimeStr = minutesToTime(currentTime + duration);

        // Add to schedule
        schedule.push({
            todo_id: todo.id,
            description: todo.description,
            priority: todo.priority,
            start_time: startTimeStr,
            end_time: endTimeStr,
            duration_minutes: duration
        });

        // Update current time and scheduled minutes
        currentTime += duration;
        scheduledMinutes += duration;
    });

    return {
        schedule: schedule,
        total_scheduled_minutes: scheduledMinutes,
        utilization_percentage: Math.round((scheduledMinutes / availableMins) * 100)
    };
}

// Generate the schedule
const scheduleResults = generateSchedule(pendingTodos, startMinutes, availableMinutes);

// Prepare final schedule data
const scheduleData = {
    date: targetDate,
    weekday: weekday,
    working_hours: workingHours,
    schedule: scheduleResults.schedule,
    total_tasks: scheduleResults.schedule.length,
    total_scheduled_minutes: scheduleResults.total_scheduled_minutes,
    available_minutes: availableMinutes,
    utilization_percentage: scheduleResults.utilization_percentage
};

// Return the schedule data for publishing
return {
    payload: scheduleData,
    topic: "todo/dashboard/schedule"
};
