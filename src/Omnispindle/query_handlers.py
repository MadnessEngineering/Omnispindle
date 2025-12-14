"""
Enhanced query handlers for metadata filtering and search capabilities.

Provides advanced filtering for standardized metadata fields including:
- Array field filtering (tags, files, components, etc.)
- Enum field filtering (complexity, priority)  
- Numeric range filtering (confidence)
- Date range filtering
- Text search within metadata
"""

import logging
import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union

logger = logging.getLogger(__name__)


class MetadataQueryBuilder:
    """Builds MongoDB queries for metadata filtering."""
    
    @staticmethod
    def build_tags_filter(tags: Union[str, List[str]], operator: str = "$in") -> Dict[str, Any]:
        """
        Build filter for tags array field.
        
        Args:
            tags: Single tag or list of tags
            operator: MongoDB operator ($in, $all, $nin)
            
        Returns:
            MongoDB query filter
        """
        if isinstance(tags, str):
            tags = [tags]
        
        return {"metadata.tags": {operator: tags}}
    
    @staticmethod
    def build_complexity_filter(complexity: Union[str, List[str]]) -> Dict[str, Any]:
        """Build filter for complexity enum field."""
        valid_complexity = ["Low", "Medium", "High", "Complex"]
        
        if isinstance(complexity, str):
            complexity = [complexity]
        
        # Validate complexity values
        filtered_complexity = [c for c in complexity if c in valid_complexity]
        if not filtered_complexity:
            logger.warning(f"No valid complexity values provided: {complexity}")
            return {}
        
        return {"metadata.complexity": {"$in": filtered_complexity}}
    
    @staticmethod 
    def build_confidence_filter(min_confidence: Optional[int] = None, 
                               max_confidence: Optional[int] = None) -> Dict[str, Any]:
        """
        Build filter for confidence numeric field (1-5).
        
        Args:
            min_confidence: Minimum confidence level
            max_confidence: Maximum confidence level
            
        Returns:
            MongoDB query filter
        """
        filter_conditions = {}
        
        if min_confidence is not None:
            filter_conditions["$gte"] = max(1, min_confidence)
        
        if max_confidence is not None:
            filter_conditions["$lte"] = min(5, max_confidence)
        
        if filter_conditions:
            return {"metadata.confidence": filter_conditions}
        
        return {}
    
    @staticmethod
    def build_phase_filter(phase: Union[str, List[str]]) -> Dict[str, Any]:
        """Build filter for phase field."""
        if isinstance(phase, str):
            phase = [phase]
        
        return {"metadata.phase": {"$in": phase}}
    
    @staticmethod
    def build_files_filter(files: Union[str, List[str]], 
                          match_type: str = "partial") -> Dict[str, Any]:
        """
        Build filter for files array field.
        
        Args:
            files: File path(s) to search for
            match_type: "exact", "partial", or "extension"
            
        Returns:
            MongoDB query filter
        """
        if isinstance(files, str):
            files = [files]
        
        if match_type == "exact":
            return {"metadata.files": {"$in": files}}
        elif match_type == "partial":
            # Use regex for partial matches
            regex_patterns = [{"metadata.files": {"$regex": re.escape(f), "$options": "i"}} 
                            for f in files]
            return {"$or": regex_patterns}
        elif match_type == "extension":
            # Filter by file extensions
            regex_patterns = [{"metadata.files": {"$regex": f"\\.{ext}$", "$options": "i"}} 
                            for ext in files]
            return {"$or": regex_patterns}
        
        return {}
    
    @staticmethod
    def build_date_range_filter(field: str, start_date: Optional[int] = None, 
                               end_date: Optional[int] = None) -> Dict[str, Any]:
        """
        Build date range filter for timestamp fields.
        
        Args:
            field: Field name (created_at, updated_at, completed_at)
            start_date: Start timestamp (unix)
            end_date: End timestamp (unix)
            
        Returns:
            MongoDB query filter
        """
        filter_conditions = {}
        
        if start_date is not None:
            filter_conditions["$gte"] = start_date
        
        if end_date is not None:
            filter_conditions["$lte"] = end_date
        
        if filter_conditions:
            return {field: filter_conditions}
        
        return {}
    
    @staticmethod
    def build_metadata_text_search(query: str, 
                                  fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Build text search within metadata fields.
        
        Args:
            query: Search text
            fields: Specific metadata fields to search (default: all text fields)
            
        Returns:
            MongoDB query filter
        """
        if not fields:
            # Default searchable metadata fields
            fields = [
                "metadata.phase",
                "metadata.current_state", 
                "metadata.target_state",
                "metadata.custom"
            ]
        
        # Build regex search for each field
        regex_conditions = []
        for field in fields:
            regex_conditions.append({
                field: {"$regex": re.escape(query), "$options": "i"}
            })
        
        return {"$or": regex_conditions} if regex_conditions else {}


class TodoQueryEnhancer:
    """Enhanced query capabilities for todos with metadata filtering."""
    
    def __init__(self):
        self.query_builder = MetadataQueryBuilder()
    
    def enhance_query_filter(self, base_filter: Dict[str, Any], 
                           metadata_filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhance base MongoDB filter with metadata-specific filters.
        
        Args:
            base_filter: Existing MongoDB filter
            metadata_filters: Metadata filter specifications
            
        Returns:
            Enhanced MongoDB filter
        """
        enhanced_filter = base_filter.copy()
        conditions = []
        
        # Add base filter as first condition if not empty
        if base_filter:
            conditions.append(base_filter)
        
        # Process metadata filters
        for filter_type, filter_value in metadata_filters.items():
            if filter_type == "tags":
                if isinstance(filter_value, dict):
                    operator = filter_value.get("operator", "$in")
                    tags = filter_value.get("values", [])
                else:
                    operator = "$in"
                    tags = filter_value
                
                tag_filter = self.query_builder.build_tags_filter(tags, operator)
                if tag_filter:
                    conditions.append(tag_filter)
            
            elif filter_type == "complexity":
                complexity_filter = self.query_builder.build_complexity_filter(filter_value)
                if complexity_filter:
                    conditions.append(complexity_filter)
            
            elif filter_type == "confidence":
                if isinstance(filter_value, dict):
                    min_conf = filter_value.get("min")
                    max_conf = filter_value.get("max")
                else:
                    min_conf = filter_value
                    max_conf = None
                
                confidence_filter = self.query_builder.build_confidence_filter(min_conf, max_conf)
                if confidence_filter:
                    conditions.append(confidence_filter)
            
            elif filter_type == "phase":
                phase_filter = self.query_builder.build_phase_filter(filter_value)
                if phase_filter:
                    conditions.append(phase_filter)
            
            elif filter_type == "files":
                if isinstance(filter_value, dict):
                    files = filter_value.get("files", [])
                    match_type = filter_value.get("match_type", "partial")
                else:
                    files = filter_value
                    match_type = "partial"
                
                files_filter = self.query_builder.build_files_filter(files, match_type)
                if files_filter:
                    conditions.append(files_filter)
            
            elif filter_type == "date_range":
                field = filter_value.get("field", "created_at")
                start_date = filter_value.get("start")
                end_date = filter_value.get("end")
                
                date_filter = self.query_builder.build_date_range_filter(field, start_date, end_date)
                if date_filter:
                    conditions.append(date_filter)
            
            elif filter_type == "metadata_search":
                search_query = filter_value.get("query", "")
                fields = filter_value.get("fields")
                
                search_filter = self.query_builder.build_metadata_text_search(search_query, fields)
                if search_filter:
                    conditions.append(search_filter)
        
        # Combine all conditions
        if len(conditions) == 0:
            return {}
        elif len(conditions) == 1:
            return conditions[0]
        else:
            return {"$and": conditions}
    
    def build_aggregation_pipeline(self, base_filter: Dict[str, Any],
                                 metadata_filters: Dict[str, Any],
                                 sort_options: Optional[Dict[str, Any]] = None,
                                 limit: int = 100) -> List[Dict[str, Any]]:
        """
        Build MongoDB aggregation pipeline with metadata filtering.
        
        Args:
            base_filter: Base MongoDB filter
            metadata_filters: Metadata-specific filters
            sort_options: Sort specifications
            limit: Result limit
            
        Returns:
            MongoDB aggregation pipeline
        """
        pipeline = []
        
        # Match stage
        match_filter = self.enhance_query_filter(base_filter, metadata_filters)
        if match_filter:
            pipeline.append({"$match": match_filter})
        
        # Add metadata analysis stage if needed
        if any(key.startswith("metadata") for key in metadata_filters.keys()):
            pipeline.append({
                "$addFields": {
                    "metadata_score": {
                        "$cond": {
                            "if": {"$ne": ["$metadata", None]},
                            "then": {"$size": {"$objectToArray": "$metadata"}},
                            "else": 0
                        }
                    }
                }
            })
        
        # Sort stage
        if sort_options:
            pipeline.append({"$sort": sort_options})
        else:
            # Default sort by created_at descending
            pipeline.append({"$sort": {"created_at": -1}})
        
        # Limit stage
        pipeline.append({"$limit": limit})
        
        return pipeline


# Global enhancer instance
_query_enhancer = TodoQueryEnhancer()

def get_query_enhancer() -> TodoQueryEnhancer:
    """Get global query enhancer instance."""
    return _query_enhancer

def enhance_todo_query(base_filter: Dict[str, Any], 
                      metadata_filters: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience function to enhance todo queries."""
    return _query_enhancer.enhance_query_filter(base_filter, metadata_filters)

def build_metadata_aggregation(base_filter: Dict[str, Any],
                              metadata_filters: Dict[str, Any],
                              **kwargs) -> List[Dict[str, Any]]:
    """Convenience function to build aggregation pipelines.""" 
    return _query_enhancer.build_aggregation_pipeline(
        base_filter, metadata_filters, **kwargs
    )