// Generate tomorrow's date in YYYY-MM-DD format
const tomorrow = new Date();
tomorrow.setDate(tomorrow.getDate() + 1);
const formattedDate = tomorrow.toISOString().split('T')[0];

return {
    payload: { date: formattedDate },
    topic: "todo/action/daily_schedule"
};
