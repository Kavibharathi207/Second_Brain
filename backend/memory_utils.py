"""
Utility functions for memory management
Includes memory decay, prioritization, emotional tone, deadline parsing, and export/import
"""

import re
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from .memory_store import memory_store
from .config import config


class MemoryDecayManager:
    """Manages memory decay and importance scoring"""

    def __init__(self):
        self.decay_factor = config.DECAY_FACTOR
        self.decay_enabled = config.MEMORY_DECAY_ENABLED

    def calculate_decay_score(self, memory: Dict[str, Any]) -> float:
        """
        Priority Score = Importance × Recency × Access Frequency
        """
        metadata = memory.get("metadata", {})
        importance = float(metadata.get("importance", 1.0))

        created_at = metadata.get("created_at")
        if created_at:
            try:
                created = datetime.fromisoformat(created_at)
                days_old = (datetime.now() - created).days
                recency = self.decay_factor ** (days_old / 30.0)
            except Exception:
                recency = 1.0
        else:
            recency = 1.0

        access_count = int(metadata.get("access_count", 0))
        access_factor = 1.0 + (access_count * 0.05)

        return round(min(importance * recency * access_factor, 1.0), 4)

    def update_all_importance_scores(self):
        if not self.decay_enabled:
            return
        for memory in memory_store.get_all_memories():
            score = self.calculate_decay_score(memory)
            meta = memory.get("metadata", {})
            meta["importance"] = score
            memory_store.update_memory(memory["id"], metadata=meta)

    def get_important_memories(self, min_score: float = 0.5) -> List[Dict[str, Any]]:
        all_memories = memory_store.get_all_memories()
        important = [m for m in all_memories if self.calculate_decay_score(m) >= min_score]
        return sorted(important, key=self.calculate_decay_score, reverse=True)


class EmotionalToneDetector:
    """Detect emotional tone from memory content"""

    POSITIVE = ["happy", "excited", "great", "amazing", "love", "wonderful", "fantastic",
                "proud", "grateful", "joy", "success", "achieved", "win", "excellent"]
    NEGATIVE = ["sad", "angry", "frustrated", "worried", "anxious", "stressed", "failed",
                "disappointed", "upset", "fear", "hate", "terrible", "awful", "bad"]
    URGENT   = ["urgent", "asap", "immediately", "critical", "emergency", "deadline",
                "must", "important", "vital", "essential", "now", "today", "tonight"]

    @classmethod
    def detect(cls, content: str) -> Dict[str, Any]:
        lower = content.lower()
        pos = sum(1 for w in cls.POSITIVE if w in lower)
        neg = sum(1 for w in cls.NEGATIVE if w in lower)
        urg = sum(1 for w in cls.URGENT  if w in lower)

        if urg > 0:
            tone, emoji = "urgent", "🚨"
        elif pos > neg:
            tone, emoji = "positive", "😊"
        elif neg > pos:
            tone, emoji = "negative", "😟"
        else:
            tone, emoji = "neutral", "😐"

        return {"tone": tone, "emoji": emoji, "positive_signals": pos,
                "negative_signals": neg, "urgency_signals": urg}


class DeadlineExtractor:
    """Extract and parse deadlines from memory content"""

    RELATIVE = {
        "today": 0, "tonight": 0, "tomorrow": 1, "day after tomorrow": 2,
        "next week": 7, "next month": 30, "this week": 7,
        "in 2 days": 2, "in 3 days": 3, "in a week": 7,
    }
    WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

    @classmethod
    def extract(cls, content: str) -> Optional[Dict[str, Any]]:
        lower = content.lower()

        for phrase, days in cls.RELATIVE.items():
            if phrase in lower:
                deadline_dt = datetime.now() + timedelta(days=days)
                return {
                    "detected": True,
                    "phrase": phrase,
                    "date": deadline_dt.strftime("%Y-%m-%d"),
                    "days_until": days,
                    "display": deadline_dt.strftime("%b %d, %Y"),
                }

        for i, day in enumerate(cls.WEEKDAYS):
            if day in lower:
                today_idx = datetime.now().weekday()
                days_ahead = (i - today_idx) % 7 or 7
                deadline_dt = datetime.now() + timedelta(days=days_ahead)
                return {
                    "detected": True,
                    "phrase": day,
                    "date": deadline_dt.strftime("%Y-%m-%d"),
                    "days_until": days_ahead,
                    "display": deadline_dt.strftime("%b %d, %Y"),
                }

        # Match patterns like "Jan 15", "15th January", "2024-12-31"
        date_patterns = [
            r'\b(\d{4}-\d{2}-\d{2})\b',
            r'\b(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})\b',
        ]
        for pattern in date_patterns:
            match = re.search(pattern, content)
            if match:
                return {
                    "detected": True,
                    "phrase": match.group(),
                    "date": match.group(),
                    "days_until": None,
                    "display": match.group(),
                }

        return {"detected": False}


class MemoryParser:
    """Parse and extract information from memory entries"""

    @staticmethod
    def detect_memory_type(content: str) -> str:
        """Detect memory type from content keywords"""
        lower = content.lower()
        if any(w in lower for w in ["meeting", "appointment", "event", "birthday", "party", "conference"]):
            return "Event"
        if any(w in lower for w in ["task", "todo", "deadline", "submit", "exam", "due", "finish", "complete", "buy", "call"]):
            return "Task"
        if any(w in lower for w in ["learned", "study", "note", "research", "read", "book", "course", "tutorial"]):
            return "Knowledge"
        return "Personal"

    @staticmethod
    def extract_tags(content: str) -> List[str]:
        words = content.split()
        tags = [w[1:].lower().strip(".,!?") for w in words if w.startswith("#") and len(w) > 1]
        return list(dict.fromkeys(tags))

    @staticmethod
    def extract_deadlines(content: str) -> List[str]:
        result = DeadlineExtractor.extract(content)
        if result and result.get("detected"):
            return [result["display"]]
        return []

    @staticmethod
    def calculate_content_importance(content: str) -> float:
        score = 0.5
        lower = content.lower()
        high_words = ["important", "urgent", "critical", "deadline", "must",
                      "essential", "vital", "priority", "exam", "submit", "due"]
        low_words  = ["maybe", "optional", "could", "consider", "might", "someday"]
        for w in high_words:
            if w in lower:
                score += 0.15
        for w in low_words:
            if w in lower:
                score -= 0.1
        return round(min(max(score, 0.0), 1.0), 2)

    @staticmethod
    def get_upcoming_deadlines(days_ahead: int = 7) -> List[Dict[str, Any]]:
        """Get memories with upcoming deadlines"""
        all_memories = memory_store.get_all_memories()
        upcoming = []
        cutoff = datetime.now() + timedelta(days=days_ahead)
        
        for memory in all_memories:
            deadline_info = DeadlineExtractor.extract(memory["content"])
            if deadline_info and deadline_info["detected"]:
                try:
                    deadline_date = datetime.fromisoformat(deadline_info["date"])
                    if deadline_date <= cutoff and deadline_date >= datetime.now():
                        upcoming.append({
                            "memory_id": memory["id"],
                            "content": memory["content"],
                            "deadline": deadline_info,
                            "metadata": memory["metadata"]
                        })
                except Exception:
                    pass
        return upcoming


class MemoryStatistics:
    """Generate statistics about stored memories"""

    @staticmethod
    def get_statistics() -> Dict[str, Any]:
        all_memories = memory_store.get_all_memories()

        if not all_memories:
            return {
                "total_memories": 0, "total_characters": 0,
                "average_length": 0, "tags": {},
                "creation_date_range": None, "type_breakdown": {},
                "tone_breakdown": {}, "avg_importance": 0.0,
            }

        total_chars = sum(len(m.get("content", "")) for m in all_memories)
        avg_length  = total_chars // len(all_memories)

        tag_counts, type_counts, tone_counts = {}, {}, {}
        importance_scores = []

        for m in all_memories:
            content  = m.get("content", "")
            metadata = m.get("metadata", {})

            for tag in MemoryParser.extract_tags(content):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

            mtype = metadata.get("memory_type") or MemoryParser.detect_memory_type(content)
            type_counts[mtype] = type_counts.get(mtype, 0) + 1

            tone = EmotionalToneDetector.detect(content)["tone"]
            tone_counts[tone] = tone_counts.get(tone, 0) + 1

            importance_scores.append(float(metadata.get("importance", 0.5)))

        dates = [m.get("metadata", {}).get("created_at", "") for m in all_memories if m.get("metadata", {}).get("created_at")]

        return {
            "total_memories": len(all_memories),
            "total_characters": total_chars,
            "average_length": avg_length,
            "tags": tag_counts,
            "creation_date_range": {"oldest": min(dates) if dates else None, "newest": max(dates) if dates else None},
            "type_breakdown": type_counts,
            "tone_breakdown": tone_counts,
            "avg_importance": round(sum(importance_scores) / len(importance_scores), 2) if importance_scores else 0.0,
        }


class MemoryExporter:
    """Export and import memories"""

    @staticmethod
    def export_json() -> str:
        memories = memory_store.get_all_memories()
        export_data = {
            "exported_at": datetime.now().isoformat(),
            "total": len(memories),
            "memories": [
                {"id": m["id"], "content": m["content"], "metadata": m["metadata"]}
                for m in memories
            ]
        }
        return json.dumps(export_data, indent=2, default=str)

    @staticmethod
    def import_json(json_str: str) -> Tuple[int, int]:
        """Returns (imported_count, failed_count)"""
        imported, failed = 0, 0
        try:
            data = json.loads(json_str)
            memories = data.get("memories", [])
            for m in memories:
                try:
                    memory_store.store_memory(
                        content=m["content"],
                        metadata=m.get("metadata", {}),
                        memory_id=m.get("id")
                    )
                    imported += 1
                except Exception:
                    failed += 1
        except Exception:
            failed += 1
        return imported, failed


# Global instances
memory_decay  = MemoryDecayManager()
memory_parser = MemoryParser()
memory_stats  = MemoryStatistics()
tone_detector = EmotionalToneDetector()
deadline_extractor = DeadlineExtractor()
memory_exporter    = MemoryExporter()
