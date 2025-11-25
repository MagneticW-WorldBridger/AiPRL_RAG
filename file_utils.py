import re
from typing import List, Set
import json


def extract_tags_from_text(content: str, max_tags: int = 10) -> List[str]:
    """
    Extract tags from text content for hybrid retrieval.
    This is a simple implementation - you can enhance it with NLP libraries.
    """
    # Convert to lowercase
    content_lower = content.lower()
    
    # Remove special characters and split into words
    words = re.findall(r'\b[a-z]{3,}\b', content_lower)
    
    # Filter out common stop words
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
        'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
        'should', 'could', 'may', 'might', 'must', 'can', 'this', 'that',
        'these', 'those', 'it', 'its', 'they', 'them', 'their', 'there'
    }
    
    # Count word frequencies
    word_freq = {}
    for word in words:
        if word not in stop_words and len(word) > 3:
            word_freq[word] = word_freq.get(word, 0) + 1
    
    # Get top tags by frequency
    sorted_tags = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
    tags = [tag for tag, _ in sorted_tags[:max_tags]]
    
    return tags


def tags_to_json(tags: List[str]) -> str:
    """Convert tags list to JSON string"""
    return json.dumps(tags)


def json_to_tags(json_str: str) -> List[str]:
    """Convert JSON string to tags list"""
    if not json_str:
        return []
    try:
        return json.loads(json_str)
    except:
        return []

