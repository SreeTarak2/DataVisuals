from datetime import datetime
from typing import List, Optional, Dict, Any
from bson import ObjectId
import json


class BeliefService:
    def __init__(self, db):
        self.db = db
        self.collection = db.beliefs

    async def get_active_beliefs(self, user_id: str, dataset_id: str) -> List[Dict]:
        cursor = (
            self.collection.find({"user_id": user_id, "dataset_id": dataset_id, "active": True})
            .sort("usage_count", -1)
            .limit(20)
        )
        beliefs = []
        async for b in cursor:
            b["_id"] = str(b["_id"])
            beliefs.append(b)
        return beliefs

    async def format_for_prompt(self, user_id: str, dataset_id: str) -> str:
        beliefs = await self.get_active_beliefs(user_id, dataset_id)
        if not beliefs:
            return ""
        lines = ["## Business Rules — follow these EXACTLY, no exceptions:"]
        for i, b in enumerate(beliefs, 1):
            lines.append(f"{i}. {b['content']}")
        return "\n".join(lines)

    async def extract_and_save(
        self,
        user_id: str,
        dataset_id: str,
        user_message: str,
        previous_ai_response: str,
    ) -> Optional[Dict]:
        from services.llm.router import llm_router

        prompt = f"""Analyze if this user message is correcting or refining an AI analysis.

Previous AI response: {previous_ai_response[:400]}

User message: {user_message}

If this IS a correction or business rule, extract it as a precise reusable rule.
If NOT a correction (new question, greeting, etc.), return null.

Respond ONLY with valid JSON, no markdown:

If correction:
{{"is_correction": true, "rule": "Revenue must exclude refunds", "rule_type": "metric_definition", "applies_to": ["revenue"], "confidence": 0.9}}

If not:
{{"is_correction": false}}

rule_type: metric_definition | filter_rule | join_rule | exclusion_rule | business_logic"""

        try:
            response = await llm_router.call(
                prompt=prompt,
                model_role="conversational",
                expect_json=True,
                temperature=0.1,
                max_tokens=300,
            )
            content = response
            if isinstance(content, str):
                content = content.strip().strip("```json").strip("```").strip()
                result = json.loads(content)
            elif isinstance(content, dict):
                result = content
            else:
                return None

            if not result.get("is_correction"):
                return None

            existing = await self.collection.find_one(
                {
                    "user_id": user_id,
                    "dataset_id": dataset_id,
                    "content": {"$regex": result["rule"][:25], "$options": "i"},
                    "active": True,
                }
            )
            if existing:
                await self.collection.update_one(
                    {"_id": existing["_id"]},
                    {
                        "$inc": {"confidence": 0.05, "reinforcement_count": 1},
                        "$set": {"updated_at": datetime.utcnow()},
                    },
                )
                existing["_id"] = str(existing["_id"])
                existing["_reinforced"] = True
                return existing

            doc = {
                "user_id": user_id,
                "dataset_id": dataset_id,
                "content": result["rule"],
                "rule_type": result.get("rule_type", "business_logic"),
                "applies_to": result.get("applies_to", []),
                "confidence": result.get("confidence", 0.8),
                "usage_count": 0,
                "reinforcement_count": 1,
                "active": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "source_message": user_message[:200],
            }
            res = await self.collection.insert_one(doc)
            doc["_id"] = str(res.inserted_id)
            return doc

        except Exception as e:
            print(f"[BeliefService] extract error (non-fatal): {e}")
            return None

    async def increment_usage(self, belief_ids: List[str]):
        for bid in belief_ids:
            try:
                await self.collection.update_one(
                    {"_id": ObjectId(bid)}, {"$inc": {"usage_count": 1}}
                )
            except Exception:
                pass

    async def list_all(self, user_id: str, dataset_id: str) -> List[Dict]:
        cursor = self.collection.find({"user_id": user_id, "dataset_id": dataset_id}).sort(
            "created_at", -1
        )
        out = []
        async for b in cursor:
            b["_id"] = str(b["_id"])
            out.append(b)
        return out

    async def save_manual(
        self, user_id: str, dataset_id: str, content: str, rule_type: str = "business_logic"
    ) -> Dict:
        doc = {
            "user_id": user_id,
            "dataset_id": dataset_id,
            "content": content,
            "rule_type": rule_type,
            "applies_to": [],
            "confidence": 1.0,
            "usage_count": 0,
            "reinforcement_count": 1,
            "active": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "source_message": "manual",
        }
        res = await self.collection.insert_one(doc)
        doc["_id"] = str(res.inserted_id)
        return doc

    async def update(self, belief_id: str, user_id: str, content: str) -> bool:
        r = await self.collection.update_one(
            {"_id": ObjectId(belief_id), "user_id": user_id},
            {"$set": {"content": content, "updated_at": datetime.utcnow()}},
        )
        return r.modified_count > 0

    async def deactivate(self, belief_id: str, user_id: str) -> bool:
        r = await self.collection.update_one(
            {"_id": ObjectId(belief_id), "user_id": user_id},
            {"$set": {"active": False, "updated_at": datetime.utcnow()}},
        )
        return r.modified_count > 0
