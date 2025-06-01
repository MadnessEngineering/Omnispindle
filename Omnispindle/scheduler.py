"""
Task Auto-Scheduling Module for FastMCP Todo Server

This module provides intelligent task scheduling capabilities including:
- Deadline suggestions based on task priority and estimated completion time
- Work pattern analysis to find optimal time slots for tasks
- Calendar integration for scheduling suggestions
- Workload balancing to prevent overallocation
"""

import json
import logging
import os
from datetime import datetime, timedelta, UTC, time
from typing import Dict, List, Optional, Tuple, Any
import random
import calendar
from collections import defaultdict

from pymongo import MongoClient
from .ai_assistant import assistant as todo_assistant
from . import mqtt_publish

# Configure logger
logger = logging.getLogger(__name__)

# Load MongoDB connection from environment
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.getenv("MONGODB_DB", "swarmonomicon")
MONGODB_COLLECTION = os.getenv("MONGODB_COLLECTION", "todos")

# Create MongoDB connection
mongo_client = MongoClient(MONGODB_URI)
db = mongo_client[MONGODB_DB]
collection = db[MONGODB_COLLECTION]

# Constants for scheduling
WORKING_HOURS = {
    # Weekday: [(start_hour, start_minute), (end_hour, end_minute)]
    0: [(9, 0), (17, 0)],  # Monday
    1: [(9, 0), (17, 0)],  # Tuesday
    2: [(9, 0), (17, 0)],  # Wednesday
    3: [(9, 0), (17, 0)],  # Thursday
    4: [(9, 0), (17, 0)],  # Friday
    5: [(10, 0), (14, 0)],  # Saturday (reduced hours)
    6: [],  # Sunday (no hours)
}

# Priority to deadline mapping (in days)
PRIORITY_DEADLINES = {
    "high": 2,
    "medium": 5,
    "low": 10,
    "initial": 7,
}

# Priority to time slot duration mapping (in minutes)
PRIORITY_DURATION = {
    "high": 120,  # 2 hours
    "medium": 90,  # 1.5 hours
    "low": 60,  # 1 hour
    "initial": 90,  # 1.5 hours
}



# @register_tool_once
# async def get_todo_suggestions_tool() -> str:
#     """
#     Get AI-powered suggestions for todos based on pattern analysis.

#     This tool analyzes completed todos to identify patterns and makes suggestions for:
#     1. Task automation opportunities
#     2. Priority recommendations for pending todos
#     3. Insights about task patterns

#     Returns:
#         A JSON string containing suggestions and analysis results
#     """
#     return await get_todo_suggestions()


# @register_tool_once
# async def get_specific_todo_suggestions_tool(todo_id: str) -> str:
#     """
#     Get AI-powered suggestions for a specific todo.

#     This tool analyzes a specific todo and compares it with completed todos to provide:
#     1. Priority recommendations based on similar completed todos
#     2. Estimated completion time based on similar tasks
#     3. List of similar completed todos for reference

#     Args:
#         todo_id: ID of the todo to get suggestions for

#     Returns:
#         A JSON string containing suggestions specific to the todo
#     """
#     return await get_specific_suggestions(todo_id)


# @register_tool_once
# async def suggest_deadline_tool(todo_id: str) -> str:
#     """
#     Suggest an optimal deadline for a specific todo based on priority and content analysis.

#     This tool analyzes a todo's priority and description to suggest a reasonable deadline:
#     1. High priority tasks get shorter deadlines
#     2. Keywords like "urgent" or "tomorrow" influence the suggestion
#     3. The deadline always falls on a working day

#     The returned data includes:
#     - Suggested deadline date with reasoning
#     - Adjustment factors that were considered
#     - Possible next actions after setting a deadline

#     Args:
#         todo_id: ID of the todo to suggest a deadline for

#     Returns:
#         A JSON string containing the deadline suggestion with detailed reasoning
#     """
#     result = await suggest_deadline(todo_id)

#     # Add tool-specific hints for AI agents to better understand response format
#     try:
#         data = json.loads(result)
#         if data.get("success") and "data" in data:
#             deadline_data = data["data"]
#             # Add usage examples if not already present
#             if "ai_agent_hints" not in deadline_data:
#                 deadline_data["ai_agent_hints"] = {
#                     "explanation": "This suggests a deadline of " +
#                                   deadline_data.get("suggested_deadline", {}).get("date", "unknown") +
#                                   " for the todo item, based on its priority and content analysis.",
#                     "reasoning_breakdown": "The reasoning field explains how the deadline was determined, including base priority rules, keyword modifiers, and weekend adjustments.",
#                     "response_formats": [
#                         "I suggest completing this task by {suggested_deadline.date} ({suggested_deadline.day_of_week}), which is {suggested_deadline.days_from_now} days from now.",
#                         "Based on this being a {todo_priority} priority task, I recommend a deadline of {suggested_deadline.date}.",
#                         "The deadline of {suggested_deadline.date} was chosen because: {reasoning.summary}"
#                     ]
#                 }
#             data["data"] = deadline_data
#             result = json.dumps(data)
#     except Exception as e:
#         print(f"Error enhancing deadline response: {str(e)}")

#     return result


# @register_tool_once
# async def suggest_time_slot_tool(todo_id: str, date: Optional[str] = None) -> str:
#     """
#     Suggest an optimal time slot for completing a specific todo.

#     This tool analyzes completed todos to find patterns in when similar tasks
#     are typically completed, then suggests an optimal time slot:
#     1. Based on historical completion patterns for similar tasks
#     2. Considering the priority of the task (high priority = morning slots)
#     3. Using appropriate duration based on task priority

#     Args:
#         todo_id: ID of the todo to schedule
#         date: Optional specific date in YYYY-MM-DD format

#     Returns:
#         A JSON string containing the time slot suggestion with reasoning
#     """
#     return await suggest_time_slot(todo_id, date)


# @register_tool_once
# async def generate_daily_schedule_tool(date: Optional[str] = None) -> str:
#     """
#     Generate an optimized daily schedule based on pending todos.

#     This tool creates a complete daily schedule by:
#     1. Prioritizing tasks based on their importance
#     2. Allocating appropriate time slots with breaks between tasks
#     3. Ensuring the schedule respects working hours
#     4. Limiting the number of tasks to a reasonable amount per day

#     Args:
#         date: Optional specific date in YYYY-MM-DD format (defaults to tomorrow)

#     Returns:
#         A JSON string containing the complete suggested schedule
#     """
#     return await generate_daily_schedule(date)



class TodoScheduler:
    """AI-powered Todo Scheduler that suggests optimal times for tasks"""

    def __init__(self):
        """Initialize the Todo Scheduler"""
        self.completed_todos = []
        self.pending_todos = []
        self.completion_patterns = {}
        self.scheduled_slots = []
        self.last_refresh = None
        logger.info("Todo Scheduler initialized")

    def refresh_data(self) -> None:
        """Fetch fresh todo data from the database"""
        # Use the assistant to get todo data since it already has the logic
        todo_assistant.refresh_data()
        self.completed_todos = todo_assistant.completed_todos
        self.pending_todos = todo_assistant.pending_todos
        self.analyze_completion_patterns()
        self.last_refresh = datetime.now(UTC)
        logger.info("Scheduler refreshed data from Todo Assistant")

    def analyze_completion_patterns(self) -> Dict[int, List[int]]:
        """
        Analyze when todos are typically completed to identify optimal work times
        
        Returns:
            Dictionary mapping weekdays to hour frequencies
        """
        patterns = defaultdict(lambda: defaultdict(int))

        # Analyze completion times from completed todos
        for todo in self.completed_todos:
            if todo.get("completed_at"):
                # Convert timestamp to datetime
                try:
                    completed_time = datetime.fromtimestamp(todo.get("completed_at"), UTC)
                    weekday = completed_time.weekday()  # 0-6 (Monday is 0)
                    hour = completed_time.hour

                    # Increment count for this weekday+hour
                    patterns[weekday][hour] += 1
                except (TypeError, ValueError) as e:
                    logger.warning(f"Invalid timestamp in todo {todo.get('id')}: {e}")

        # Store the results
        self.completion_patterns = dict(patterns)

        logger.info(f"Analyzed completion patterns across {len(self.completed_todos)} todos")
        return self.completion_patterns

    def suggest_deadline(self, todo_id: str) -> Dict[str, Any]:
        """
        Suggest a deadline for a specific todo
        
        Args:
            todo_id: ID of the todo to suggest deadline for
            
        Returns:
            Dictionary with deadline suggestion and reasoning
        """
        if not self.pending_todos or self.last_refresh is None or (datetime.now(UTC) - self.last_refresh) > timedelta(minutes=30):
            self.refresh_data()

        # Find the specific todo
        todo = next((t for t in self.pending_todos if t.get("id") == todo_id), None)
        if not todo:
            # Try to get it directly from the database
            todo = collection.find_one({"id": todo_id})
            if not todo:
                logger.warning(f"Todo {todo_id} not found for deadline suggestion")
                return {
                    "status": "error",
                    "message": "Todo not found"
                }

        priority = todo.get("priority", "medium")
        description = todo.get("description", "")

        # Get estimated completion time from AI assistant if available
        completion_estimate = None
        try:
            # Find similar completed todos
            similar_todos = todo_assistant.recommend_priorities()
            for rec in similar_todos:
                if rec.get("todo_id") == todo_id:
                    # This todo has similar completed todos
                    completion_estimate = True
                    break
        except Exception as e:
            logger.warning(f"Error getting similar todos: {e}")

        # Base deadline on priority
        deadline_days = PRIORITY_DEADLINES.get(priority, 7)

        # Adjust deadline based on various factors
        if "urgent" in description.lower() or "asap" in description.lower():
            deadline_days = max(1, deadline_days - 1)
            reason = "urgent language in description"
        elif "next week" in description.lower():
            deadline_days = 7
            reason = "explicit 'next week' in description"
        elif "tomorrow" in description.lower():
            deadline_days = 1
            reason = "explicit 'tomorrow' in description"
        else:
            reason = f"standard deadline for {priority} priority"

        # Calculate the deadline date
        now = datetime.now(UTC)
        deadline_date = now + timedelta(days=deadline_days)

        # Ensure deadline falls on a working day
        while deadline_date.weekday() > 4:  # If it's a weekend
            deadline_date += timedelta(days=1)  # Move to next day

        # Format for response
        formatted_deadline = deadline_date.strftime("%Y-%m-%d")
        timestamp_deadline = int(deadline_date.timestamp())

        result = {
            "status": "success",
            "todo_id": todo_id,
            "suggested_deadline": {
                "date": formatted_deadline,
                "timestamp": timestamp_deadline,
                "days_from_now": deadline_days
            },
            "reasoning": reason,
            "priority": priority
        }

        logger.info(f"Suggested deadline for todo {todo_id}: {formatted_deadline} ({reason})")
        return result

    def suggest_time_slot(self, todo_id: str, date: Optional[str] = None) -> Dict[str, Any]:
        """
        Suggest an optimal time slot for completing a todo
        
        Args:
            todo_id: ID of the todo to schedule
            date: Optional specific date in YYYY-MM-DD format
            
        Returns:
            Dictionary with time slot suggestion and reasoning
        """
        if not self.pending_todos or not self.completion_patterns:
            self.refresh_data()

        # Find the specific todo
        todo = next((t for t in self.pending_todos if t.get("id") == todo_id), None)
        if not todo:
            # Try to get it directly from the database
            todo = collection.find_one({"id": todo_id})
            if not todo:
                logger.warning(f"Todo {todo_id} not found for time slot suggestion")
                return {
                    "status": "error",
                    "message": "Todo not found"
                }

        priority = todo.get("priority", "medium")

        # Parse date if provided, otherwise use tomorrow
        try:
            if date:
                target_date = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=UTC)
            else:
                # Default to tomorrow
                target_date = (datetime.now(UTC) + timedelta(days=1))
                # Ensure it's set to midnight for consistency
                target_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        except ValueError:
            logger.warning(f"Invalid date format: {date}")
            return {
                "status": "error",
                "message": "Invalid date format. Use YYYY-MM-DD."
            }

        weekday = target_date.weekday()

        # Check if this is a working day
        working_hours = WORKING_HOURS.get(weekday, [])
        if not working_hours:
            return {
                "status": "error",
                "message": f"The selected date ({target_date.strftime('%Y-%m-%d')}) is not a working day."
            }

        # Determine task duration based on priority
        duration_minutes = PRIORITY_DURATION.get(priority, 90)

        # Find the optimal time slot based on completion patterns
        weekday_patterns = self.completion_patterns.get(weekday, {})

        # Default working hours for this day
        start_time = time(working_hours[0][0], working_hours[0][1])
        end_time = time(working_hours[1][0], working_hours[1][1])

        # Convert to datetime objects for the target date
        start_datetime = datetime.combine(target_date.date(), start_time).replace(tzinfo=UTC)
        end_datetime = datetime.combine(target_date.date(), end_time).replace(tzinfo=UTC)

        # If we have completion patterns, use them to find optimal time
        if weekday_patterns:
            # Find the hour with the most completions
            best_hour = max(weekday_patterns.items(), key=lambda x: x[1])[0]

            # Create a time slot at this hour
            slot_start = datetime.combine(target_date.date(), time(best_hour, 0)).replace(tzinfo=UTC)

            # Ensure the slot is within working hours
            if slot_start < start_datetime:
                slot_start = start_datetime
            elif slot_start > end_datetime - timedelta(minutes=duration_minutes):
                # If the best hour is too late, use an earlier time
                slot_start = end_datetime - timedelta(minutes=duration_minutes)

            reason = f"historically productive time on {calendar.day_name[weekday]}s"
        else:
            # Without patterns, suggest morning for high priority, afternoon for others
            if priority == "high":
                # Morning slot
                slot_start = start_datetime + timedelta(hours=1)  # 1 hour after start
                reason = "high priority tasks are best done in the morning"
            else:
                # Afternoon slot
                slot_start = start_datetime + timedelta(hours=(end_datetime.hour - start_datetime.hour) // 2)
                reason = f"balanced time slot for {priority} priority tasks"

        # Calculate end time
        slot_end = slot_start + timedelta(minutes=duration_minutes)

        # Format times for response
        formatted_start = slot_start.strftime("%Y-%m-%d %H:%M")
        formatted_end = slot_end.strftime("%Y-%m-%d %H:%M")

        result = {
            "status": "success",
            "todo_id": todo_id,
            "suggested_time_slot": {
                "date": target_date.strftime("%Y-%m-%d"),
                "start_time": formatted_start,
                "end_time": formatted_end,
                "duration_minutes": duration_minutes
            },
            "reasoning": reason,
            "priority": priority
        }

        logger.info(f"Suggested time slot for todo {todo_id}: {formatted_start} - {formatted_end} ({reason})")
        return result

    def generate_daily_schedule(self, target_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate a suggested daily schedule with optimal task ordering
        
        Args:
            target_date: Optional specific date in YYYY-MM-DD format
            
        Returns:
            Dictionary with suggested schedule
        """
        if not self.pending_todos:
            self.refresh_data()

        # Parse date if provided, otherwise use tomorrow
        try:
            if target_date:
                date_obj = datetime.strptime(target_date, "%Y-%m-%d").replace(tzinfo=UTC)
            else:
                # Default to tomorrow
                date_obj = (datetime.now(UTC) + timedelta(days=1))
                # Ensure it's set to midnight for consistency
                date_obj = date_obj.replace(hour=0, minute=0, second=0, microsecond=0)
        except ValueError:
            logger.warning(f"Invalid date format: {target_date}")
            return {
                "status": "error",
                "message": "Invalid date format. Use YYYY-MM-DD."
            }

        weekday = date_obj.weekday()
        date_str = date_obj.strftime("%Y-%m-%d")

        # Check if this is a working day
        working_hours = WORKING_HOURS.get(weekday, [])
        if not working_hours:
            return {
                "status": "error",
                "message": f"The selected date ({date_str}) is not a working day."
            }

        # Start and end times for the workday
        start_time = time(working_hours[0][0], working_hours[0][1])
        end_time = time(working_hours[1][0], working_hours[1][1])

        # Convert to datetime objects for the target date
        start_datetime = datetime.combine(date_obj.date(), start_time).replace(tzinfo=UTC)
        end_datetime = datetime.combine(date_obj.date(), end_time).replace(tzinfo=UTC)

        # Calculate total available minutes
        available_minutes = (end_datetime - start_datetime).seconds // 60

        # Sort pending todos by priority
        priority_rank = {"high": 0, "medium": 1, "low": 2, "initial": 1}
        sorted_todos = sorted(
            self.pending_todos,
            key=lambda x: priority_rank.get(x.get("priority", "medium"), 999)
        )

        # Limit to a reasonable number of tasks per day
        max_todos = min(5, len(sorted_todos))
        selected_todos = sorted_todos[:max_todos]

        # Build the schedule
        schedule = []
        current_time = start_datetime
        total_scheduled_minutes = 0

        for todo in selected_todos:
            todo_id = todo.get("id")
            priority = todo.get("priority", "medium")
            description = todo.get("description", "")

            # Determine task duration
            duration_minutes = PRIORITY_DURATION.get(priority, 90)

            # Check if we have enough time left
            if total_scheduled_minutes + duration_minutes > available_minutes:
                # Not enough time left today
                continue

            # Add a 15-minute break between tasks
            if schedule:  # if not the first task
                current_time += timedelta(minutes=15)
                total_scheduled_minutes += 15

            # Calculate end time
            end_time = current_time + timedelta(minutes=duration_minutes)

            # Add to schedule
            schedule.append({
                "todo_id": todo_id,
                "description": description,
                "priority": priority,
                "start_time": current_time.strftime("%H:%M"),
                "end_time": end_time.strftime("%H:%M"),
                "duration_minutes": duration_minutes
            })

            # Update current time and total scheduled minutes
            current_time = end_time
            total_scheduled_minutes += duration_minutes

        result = {
            "status": "success",
            "date": date_str,
            "weekday": calendar.day_name[weekday],
            "working_hours": {
                "start": start_time.strftime("%H:%M"),
                "end": end_time.strftime("%H:%M")
            },
            "schedule": schedule,
            "total_tasks": len(schedule),
            "total_scheduled_minutes": total_scheduled_minutes,
            "available_minutes": available_minutes,
            "utilization_percentage": round((total_scheduled_minutes / available_minutes) * 100, 1) if available_minutes else 0
        }

        logger.info(f"Generated daily schedule for {date_str} with {len(schedule)} tasks")
        return result


# Create singleton instance
scheduler = TodoScheduler()

# async def suggest_deadline(todo_id: str) -> str:
#     """
#     Suggest an optimal deadline for a specific todo based on priority and content analysis.
#
#     This tool analyzes a todo's priority and description to suggest a reasonable deadline:
#     1. High priority tasks get shorter deadlines
#     2. Keywords like "urgent" or "tomorrow" influence the suggestion
#     3. The deadline always falls on a working day
#
#     Args:
#         todo_id: ID of the todo to suggest a deadline for
#
#     Returns:
#         A JSON string containing the deadline suggestion with reasoning
#     """
#     # First get the todo
#     todo_response = await get_todo(todo_id)
#     todo_data = json.loads(todo_response)
#
#     if not todo_data.get("success"):
#         return create_response(False, message=f"Failed to get todo: {todo_data.get('message', 'Unknown error')}")
#
#     todo = todo_data.get("data", {})
#
#     # Define deadline recommendations based on priority
#     priority_deadlines = {
#         "high": {"days": 2, "explanation": "High priority tasks should be completed quickly"},
#         "medium": {"days": 5, "explanation": "Medium priority tasks can be scheduled within a week"},
#         "low": {"days": 10, "explanation": "Low priority tasks can be scheduled within two weeks"},
#         "initial": {"days": 7, "explanation": "Tasks with initial priority are assumed to be medium importance"}
#     }
#
#     # Extract relevant information
#     priority = todo.get("priority", "initial")
#     description = todo.get("description", "")
#
#     # Start with the base deadline from priority
#     base_days = priority_deadlines.get(priority, {"days": 7, "explanation": "Default deadline for unknown priority"})
#     deadline_days = base_days["days"]
#     reasoning = [base_days["explanation"]]
#
#     # Analyze description for keywords that might affect deadline
#     deadline_modifiers = []
#
#     # Check for urgency indicators
#     urgency_keywords = {
#         "urgent": {"modifier": -1, "explanation": "Task description indicates urgency"},
#         "asap": {"modifier": -2, "explanation": "ASAP indicator suggests highest urgency"},
#         "emergency": {"modifier": -3, "explanation": "Emergency tasks require immediate attention"},
#         "critical": {"modifier": -2, "explanation": "Critical tasks need prompt attention"},
#         "immediate": {"modifier": -2, "explanation": "Immediate action required"}
#     }
#
#     for keyword, info in urgency_keywords.items():
#         if keyword in description.lower():
#             deadline_days = max(1, deadline_days + info["modifier"])
#             deadline_modifiers.append({"type": "urgency", "keyword": keyword, "days_changed": info["modifier"]})
#             reasoning.append(info["explanation"])
#
#     # Check for explicit timeframes
#     timeframe_patterns = {
#         "tomorrow": {"days": 1, "explanation": "Task explicitly mentions it's needed tomorrow"},
#         "next week": {"days": 7, "explanation": "Task is specifically scheduled for next week"},
#         "next month": {"days": 30, "explanation": "Task is scheduled for next month"},
#         "by end of week": {"days": 5, "explanation": "Task needs to be completed by the end of this week"},
#         "by end of day": {"days": 1, "explanation": "Task must be completed today"}
#     }
#
#     for phrase, info in timeframe_patterns.items():
#         if phrase in description.lower():
#             original_days = deadline_days
#             deadline_days = info["days"]
#             deadline_modifiers.append({
#                 "type": "explicit_timeframe",
#                 "keyword": phrase,
#                 "days_changed": deadline_days - original_days
#             })
#             reasoning.append(info["explanation"])
#             # If we find an explicit timeframe, it overrides other considerations
#             break
#
#     # Calculate the deadline date
#     now = datetime.now(UTC)
#     deadline_date = now + timedelta(days=deadline_days)
#
#     # Ensure deadline falls on a working day (Mon-Fri)
#     weekend_adjustment = 0
#     if deadline_date.weekday() > 4:  # If it's a weekend
#         # Move to next Monday
#         days_to_monday = 7 - deadline_date.weekday()
#         deadline_date += timedelta(days=days_to_monday)
#         weekend_adjustment = days_to_monday
#         reasoning.append(f"Adjusted deadline to next business day (moved {days_to_monday} days forward)")
#
#     # Format for response
#     formatted_deadline = deadline_date.strftime("%Y-%m-%d")
#     timestamp_deadline = int(deadline_date.timestamp())
#
#     result = {
#         "todo_id": todo_id,
#         "todo_description": description[:100] + ("..." if len(description) > 100 else ""),
#         "todo_priority": priority,
#         "suggested_deadline": {
#             "date": formatted_deadline,
#             "day_of_week": deadline_date.strftime("%A"),
#             "timestamp": timestamp_deadline,
#             "days_from_now": deadline_days + weekend_adjustment
#         },
#         "reasoning": {
#             "summary": "; ".join(reasoning),
#             "base_deadline": {
#                 "days": base_days["days"],
#                 "explanation": base_days["explanation"]
#             },
#             "modifiers": deadline_modifiers,
#             "weekend_adjustment": weekend_adjustment
#         },
#         "possible_next_actions": ["update_todo", "mark_todo_complete", "suggest_time_slot"]
#     }
#
#     # MQTT publish as confirmation after generating a deadline suggestion
#     try:
#         mqtt_message = f"todo_id: {todo_id}, deadline: {formatted_deadline}"
#         await mqtt_publish(f"status/{os.getenv('DeNa')}/omnispindle/suggest_deadline", mqtt_message)
#     except Exception as e:
#         # Log the error but don't fail the entire operation
#         print(f"MQTT publish error (non-fatal): {str(e)}")
#
#     return create_response(True, result)


async def suggest_deadline(todo_id: str) -> str:
    """
    Suggest a deadline for a specific todo
    
    Args:
        todo_id: ID of the todo to suggest deadline for
        
    Returns:
        JSON string with deadline suggestion
    """
    try:
        result = scheduler.suggest_deadline(todo_id)
        await mqtt_publish(f"status/{os.getenv('DeNa')}-mcp/suggest_deadline", json.dumps({"todo_id": todo_id, "result": result}))
        return json.dumps(result)
    except Exception as e:
        logger.error(f"Error suggesting deadline for todo {todo_id}: {e}")
        return json.dumps({"status": "error", "message": str(e)})


async def suggest_time_slot(todo_id: str, date: Optional[str] = None) -> str:
    """
    Suggest an optimal time slot for completing a todo
    
    Args:
        todo_id: ID of the todo to schedule
        date: Optional specific date in YYYY-MM-DD format
        
    Returns:
        JSON string with time slot suggestion
    """
    try:
        result = scheduler.suggest_time_slot(todo_id, date)
        await mqtt_publish(f"status/{os.getenv('DeNa')}-mcp/suggest_time_slot", json.dumps({"todo_id": todo_id, "date": date, "result": result}))
        return json.dumps(result)
    except Exception as e:
        logger.error(f"Error suggesting time slot for todo {todo_id}: {e}")
        return json.dumps({"status": "error", "message": str(e)})


async def generate_daily_schedule(date: Optional[str] = None) -> str:
    """
    Generate a suggested daily schedule with optimal task ordering
    
    Args:
        date: Optional specific date in YYYY-MM-DD format
        
    Returns:
        JSON string with suggested schedule
    """
    try:
        result = scheduler.generate_daily_schedule(date)
        await mqtt_publish(f"status/{os.getenv('DeNa')}-mcp/generate_daily_schedule", json.dumps({"date": date, "result": result}))
        return json.dumps(result)
    except Exception as e:
        logger.error(f"Error generating daily schedule: {e}")
        return json.dumps({"status": "error", "message": str(e)})
