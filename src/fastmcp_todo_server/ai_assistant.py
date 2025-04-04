"""
AI-powered Todo Assistant for FastMCP Todo Server

This module provides AI-powered features for the todo application, including:
- Pattern analysis of completed todos
- Automated suggestions for routine tasks
- Priority recommendations based on past behavior
- Task grouping and organization suggestions
"""

import json
import logging
import os
from datetime import datetime, timedelta, UTC
from typing import Dict, List, Any

from pymongo import MongoClient
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import DBSCAN
from collections import Counter

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


class TodoAssistant:
    """AI-powered Todo Assistant that learns from past todos and suggests improvements"""

    def __init__(self):
        """Initialize the Todo Assistant"""
        self.completed_todos = []
        self.pending_todos = []
        self.patterns = {}
        self.last_refresh = None
        logger.info("Todo Assistant initialized")

    def refresh_data(self) -> None:
        """Fetch fresh todo data from the database"""
        logger.debug("Refreshing todo data from database")
        try:
            # Get completed todos
            self.completed_todos = list(collection.find({"status": "completed"}))

            # Get pending todos
            self.pending_todos = list(collection.find({"status": "pending"}))

            self.last_refresh = datetime.now(UTC)
            logger.info(f"Refreshed data: {len(self.completed_todos)} completed todos, {len(self.pending_todos)} pending todos")
        except Exception as e:
            logger.error(f"Error refreshing todo data: {e}")

    def analyze_patterns(self) -> Dict[str, Any]:
        """
        Analyze patterns in completed todos to identify routine tasks
        
        Returns:
            Dict containing analysis results and patterns found
        """
        if not self.completed_todos or (self.last_refresh and (datetime.now(UTC) - self.last_refresh) > timedelta(minutes=30)):
            self.refresh_data()

        if len(self.completed_todos) < 5:
            logger.warning("Not enough completed todos for meaningful pattern analysis")
            return {"status": "insufficient_data", "message": "Need at least 5 completed todos for analysis"}

        try:
            logger.info("Starting pattern analysis on completed todos")

            # Extract descriptions
            descriptions = [todo.get("description", "") for todo in self.completed_todos]

            # Create TF-IDF vectors for text similarity
            vectorizer = TfidfVectorizer(max_features=100, stop_words='english')
            tfidf_matrix = vectorizer.fit_transform(descriptions)

            # Cluster similar todos
            dbscan = DBSCAN(eps=0.5, min_samples=2)
            clusters = dbscan.fit_predict(tfidf_matrix)

            # Find patterns
            patterns = {}
            for i, cluster_id in enumerate(clusters):
                if cluster_id != -1:  # -1 means no cluster assigned
                    if cluster_id not in patterns:
                        patterns[cluster_id] = []

                    patterns[cluster_id].append({
                        "id": self.completed_todos[i].get("id", "unknown"),
                        "description": descriptions[i],
                        "created_at": self.completed_todos[i].get("created_at"),
                        "completed_at": self.completed_todos[i].get("completed_at"),
                        "priority": self.completed_todos[i].get("priority", "medium"),
                        "target_agent": self.completed_todos[i].get("target_agent", "user")
                    })

            # Store patterns
            self.patterns = patterns

            # Calculate statistics
            total_patterns = sum(len(items) for items in patterns.values())
            num_clusters = len(patterns)

            logger.info(f"Pattern analysis complete: found {num_clusters} patterns across {total_patterns} todos")

            return {
                "status": "success",
                "patterns": patterns,
                "pattern_count": num_clusters,
                "clustered_todos": total_patterns,
                "total_completed": len(self.completed_todos)
            }

        except Exception as e:
            logger.error(f"Error in pattern analysis: {e}")
            return {"status": "error", "message": str(e)}

    def suggest_automation(self) -> List[Dict[str, Any]]:
        """
        Suggest routine tasks that could be automated based on patterns
        
        Returns:
            List of dictionaries with automation suggestions
        """
        if not self.patterns:
            self.analyze_patterns()

        suggestions = []

        # Find patterns with consistent properties worth automating
        for cluster_id, todos in self.patterns.items():
            if len(todos) >= 3:  # Need at least 3 examples to suggest automation
                # Check if target agent is consistent
                target_agents = [todo["target_agent"] for todo in todos]
                agent_counter = Counter(target_agents)
                primary_agent = agent_counter.most_common(1)[0][0]
                agent_consistency = agent_counter[primary_agent] / len(todos)

                # Check if priority is consistent
                priorities = [todo["priority"] for todo in todos]
                priority_counter = Counter(priorities)
                primary_priority = priority_counter.most_common(1)[0][0]
                priority_consistency = priority_counter[primary_priority] / len(todos)

                # Calculate average time to completion (if available)
                completion_times = []
                for todo in todos:
                    if todo.get("created_at") and todo.get("completed_at"):
                        completion_time = todo["completed_at"] - todo["created_at"]
                        if completion_time > 0:
                            completion_times.append(completion_time)

                avg_completion_time = sum(completion_times) / len(completion_times) if completion_times else None

                # Create a template based on common words
                descriptions = [todo["description"] for todo in todos]
                common_words = self._extract_common_words(descriptions)
                template = " ".join(common_words) if common_words else descriptions[0]

                # Determine if this cluster is worth automating
                automation_score = (agent_consistency + priority_consistency) / 2
                should_automate = automation_score > 0.7 and len(todos) >= 3

                if should_automate:
                    suggestion = {
                        "pattern_id": str(cluster_id),
                        "similar_tasks": len(todos),
                        "template": template,
                        "suggested_agent": primary_agent,
                        "suggested_priority": primary_priority,
                        "automation_confidence": round(automation_score * 100, 2),
                        "avg_completion_time": avg_completion_time,
                        "examples": [todo["description"] for todo in todos[:3]]
                    }
                    suggestions.append(suggestion)

        logger.info(f"Generated {len(suggestions)} automation suggestions")
        return suggestions

    def recommend_priorities(self) -> List[Dict[str, Any]]:
        """
        Recommend priority changes for pending todos based on similar completed todos
        
        Returns:
            List of dictionaries with priority recommendations
        """
        if not self.completed_todos or not self.pending_todos:
            self.refresh_data()

        recommendations = []

        # Create vectorizer from completed todos
        completed_descriptions = [todo.get("description", "") for todo in self.completed_todos]
        if not completed_descriptions:
            return recommendations

        vectorizer = TfidfVectorizer(max_features=100, stop_words='english')
        completed_vectors = vectorizer.fit_transform(completed_descriptions)

        # For each pending todo, find similar completed todos
        for pending in self.pending_todos:
            try:
                pending_desc = pending.get("description", "")
                if not pending_desc:
                    continue

                # Transform pending todo using same vectorizer
                pending_vector = vectorizer.transform([pending_desc])

                # Calculate similarity with all completed todos
                from sklearn.metrics.pairwise import cosine_similarity
                similarities = cosine_similarity(pending_vector, completed_vectors).flatten()

                # Get the indices of the top 3 most similar todos
                top_indices = similarities.argsort()[-3:][::-1]

                # Only consider valid similarities
                valid_matches = [(i, s) for i, s in zip(top_indices, similarities[top_indices]) if s > 0.3]

                if valid_matches:
                    # Get the priorities of the similar todos
                    similar_priorities = [self.completed_todos[i].get("priority", "medium") for i, _ in valid_matches]
                    priority_counter = Counter(similar_priorities)
                    recommended_priority = priority_counter.most_common(1)[0][0]

                    # Only recommend if it's different from current priority
                    current_priority = pending.get("priority", "medium")
                    if recommended_priority != current_priority:
                        recommendation = {
                            "todo_id": pending.get("id"),
                            "description": pending_desc,
                            "current_priority": current_priority,
                            "recommended_priority": recommended_priority,
                            "confidence": round((sum(s for _, s in valid_matches) / len(valid_matches)) * 100, 2),
                            "similar_tasks": len(valid_matches)
                        }
                        recommendations.append(recommendation)
            except Exception as e:
                logger.error(f"Error processing recommendation for todo {pending.get('id')}: {e}")

        logger.info(f"Generated {len(recommendations)} priority recommendations")
        return recommendations

    def _extract_common_words(self, texts: List[str], min_word_length: int = 4) -> List[str]:
        """
        Extract words that appear in multiple text descriptions
        
        Args:
            texts: List of text descriptions
            min_word_length: Minimum length of words to consider
            
        Returns:
            List of common words
        """
        # Tokenize and count word occurrences
        all_words = []
        for text in texts:
            words = [w.lower() for w in text.split() if len(w) >= min_word_length]
            all_words.extend(words)

        word_counter = Counter(all_words)

        # Words that appear in at least 50% of descriptions
        min_occurrences = max(2, len(texts) // 2)
        common_words = [word for word, count in word_counter.items() if count >= min_occurrences]

        return common_words


# Create singleton instance
assistant = TodoAssistant()


async def get_todo_suggestions() -> str:
    """
    Get AI-powered suggestions for todos based on pattern analysis
    
    Returns:
        JSON string with todo suggestions
    """
    try:
        assistant.refresh_data()

        # Get automation suggestions
        automation_suggestions = assistant.suggest_automation()

        # Get priority recommendations
        priority_recommendations = assistant.recommend_priorities()

        # Get pattern analysis
        patterns = assistant.analyze_patterns()

        result = {
            "status": "success",
            "automation_suggestions": automation_suggestions,
            "priority_recommendations": priority_recommendations,
            "pattern_analysis": {
                "total_patterns": patterns.get("pattern_count", 0),
                "analyzed_todos": patterns.get("total_completed", 0)
            }
        }

        return json.dumps(result, default=str)
    except Exception as e:
        logger.error(f"Error generating todo suggestions: {e}")
        return json.dumps({"status": "error", "message": str(e)})


async def get_specific_suggestions(todo_id: str) -> str:
    """
    Get AI-powered suggestions for a specific todo
    
    Args:
        todo_id: ID of the todo to get suggestions for
        
    Returns:
        JSON string with suggestions specific to the todo
    """
    try:
        # Get the specific todo
        todo = collection.find_one({"id": todo_id})
        if not todo:
            return json.dumps({"status": "error", "message": "Todo not found"})

        # Refresh data to ensure we have the latest information
        assistant.refresh_data()

        # For pending todos, find similar completed todos
        if todo.get("status") == "pending":
            completed_descriptions = [t.get("description", "") for t in assistant.completed_todos]
            if not completed_descriptions:
                return json.dumps({
                    "status": "success",
                    "message": "No completed todos available for comparison",
                    "suggestions": []
                })

            vectorizer = TfidfVectorizer(max_features=100, stop_words='english')
            completed_vectors = vectorizer.fit_transform(completed_descriptions)

            # Transform pending todo using same vectorizer
            pending_desc = todo.get("description", "")
            pending_vector = vectorizer.transform([pending_desc])

            # Calculate similarity with all completed todos
            from sklearn.metrics.pairwise import cosine_similarity
            similarities = cosine_similarity(pending_vector, completed_vectors).flatten()

            # Get the indices of the top 5 most similar todos
            top_indices = similarities.argsort()[-5:][::-1]

            # Only consider valid similarities
            similar_todos = []
            for i, similarity in zip(top_indices, similarities[top_indices]):
                if similarity > 0.2:
                    completed_todo = assistant.completed_todos[i]
                    similar_todos.append({
                        "id": completed_todo.get("id"),
                        "description": completed_todo.get("description"),
                        "priority": completed_todo.get("priority"),
                        "similarity": round(similarity * 100, 2)
                    })

            # Calculate suggested priority based on similar todos
            priorities = [t.get("priority") for t in similar_todos]
            priority_counter = Counter(priorities)
            suggested_priority = priority_counter.most_common(1)[0][0] if priorities else todo.get("priority")

            # Calculate estimated completion time based on similar todos
            completion_times = []
            for t in assistant.completed_todos:
                if t.get("created_at") and t.get("completed_at"):
                    completion_time = t.get("completed_at") - t.get("created_at")
                    if completion_time > 0:
                        completion_times.append(completion_time)

            avg_completion = sum(completion_times) / len(completion_times) if completion_times else None

            result = {
                "status": "success",
                "todo": {
                    "id": todo.get("id"),
                    "description": todo.get("description"),
                    "current_priority": todo.get("priority"),
                    "status": todo.get("status")
                },
                "suggestions": {
                    "suggested_priority": suggested_priority,
                    "estimated_completion_time": avg_completion,
                    "similar_completed_count": len(similar_todos)
                },
                "similar_todos": similar_todos
            }

            return json.dumps(result, default=str)

        # For completed todos, there's not much to suggest
        else:
            return json.dumps({
                "status": "success",
                "message": "Todo is already completed",
                "todo": {
                    "id": todo.get("id"),
                    "description": todo.get("description"),
                    "priority": todo.get("priority"),
                    "created_at": todo.get("created_at"),
                    "completed_at": todo.get("completed_at")
                }
            })

    except Exception as e:
        logger.error(f"Error generating suggestions for todo {todo_id}: {e}")
        return json.dumps({"status": "error", "message": str(e)})
