"""
AI conversational extractor — sends messages to OpenAI and gets natural response + structured intent.
"""

import asyncio
import json
import logging
from datetime import date

import openai
from openai import AsyncOpenAI

from app.config import get_settings
from app.ai.prompts import get_system_prompt

logger = logging.getLogger(__name__)
settings = get_settings()

# Initialize OpenAI client
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


async def extract_intent(
    message: str,
    current_date: date | None = None,
    history: list = None,
    hotel_room_types: list[dict] | None = None,
    hotel_name: str = "",
    guest_name: str | None = None,
    guest_nationality: str | None = None,
    guest_room_number: str | None = None,
) -> dict:
    """
    Send a WhatsApp message to the AI and get a natural response + structured intent.

    Returns:
        dict with 'response', 'intent' and 'data' keys.
        On failure, returns fallback response.
    """
    system_prompt = get_system_prompt(current_date, hotel_room_types, hotel_name, guest_name, guest_nationality, guest_room_number=guest_room_number)

    try:
        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": message})

        # Log full context for debugging
        logger.info(f"AI Context [Messages Count: {len(messages)}]:")
        for m in messages:
            content_snippet = m['content'][:100].replace('\n', ' ')
            logger.info(f"  - {m['role']}: {content_snippet}...")

        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            max_completion_tokens=16000,
            response_format={"type": "json_object"},
            timeout=30.0,  # o4-mini needs more time for reasoning
        )

        content = response.choices[0].message.content
        logger.info(f"AI raw response content: {content}")
        logger.info(f"AI finish_reason: {response.choices[0].finish_reason}")
        
        # o4-mini may return None content if it used all tokens for reasoning
        if not content:
            logger.warning("AI returned empty content (possible reasoning-only response)")
            return {
                "response": "عذراً واجهتنا مشكلة بسيطة، ممكن تعيد رسالتك؟ 🙏",
                "intent": None,
                "data": {},
            }
        
        content = content.strip()

        # Parse JSON
        result = json.loads(content)

        # Ensure required fields
        if "response" not in result or not result["response"]:
            result["response"] = None  # Will trigger fallback
        if "intent" not in result:
            result["intent"] = None
        if "data" not in result:
            result["data"] = {}

        return result

    except (asyncio.TimeoutError, openai.APITimeoutError):
        logger.error("AI timed out.")
        return {
            "response": "عذراً واجهتنا مشكلة بسيطة، ممكن تعيد رسالتك؟ 🙏",
            "intent": None,
            "data": {},
        }

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI response as JSON: {e}")
        return {
            "response": "عذراً واجهتنا مشكلة بسيطة، ممكن تعيد رسالتك؟ 🙏",
            "intent": None,
            "data": {},
        }

    except Exception as e:
        logger.error(f"AI extraction error: {e}")
        return {
            "response": "عذراً واجهتنا مشكلة بسيطة، ممكن تعيد رسالتك؟ 🙏",
            "intent": None,
            "data": {},
        }


async def generate_review_reply(rating: int, comment: str | None = None, category: str = "general") -> str | None:
    """
    Generate a professional Arabic reply to a guest review.
    """
    if not comment and rating >= 4:
        # Default nice response for good rating without comment
        return "شكراً جزيلاً لك على هذا التقييم الرائع! يسعدنا جداً أن إقامتك كانت مميزة، ونتطلع للترحيب بك مجدداً في أقرب وقت. 😊"
    elif not comment and rating < 4:
        return "شكراً لتقييمك. نحن نعمل دائماً على تحسين خدماتنا ونتمنى أن نرى تعليقاتك في المرة القادمة لنخدمك بشكل أفضل."
        
    prompt = f"""
أنت موظف خدمة العملاء في فندق سعودي راقٍ. 
قام أحد النزلاء بترك التقييم التالي:
- عدد النجوم: {rating}/5
- التصنيف أو القسم: {category}
- تعليق النزيل: "{comment}"

اكتب رداً احترافياً، لبقاً، وودوداً بلهجة فصحى بيضاء أو خليجية راقية جداً (لا تكن رسمياً بشكل مبالغ فيه).
إذا كان التقييم سلبياً، قدم اعتذاراً واعداً بحل المشكلة (دون وعود بتعويضات مالية). وإذا كان إيجابياً، اشكره بحرارة وعبر عن سعادتك بزيارته.
اكتب الرد فقط دون أي مقدمات أو شرح.
    """
    try:
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt.strip()}],
            max_completion_tokens=200,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Failed to generate review reply: {e}")
        return None


async def detect_recurring_complaints(new_complaint: str, past_complaints_texts: list[str]) -> dict:
    """
    Detect if the new complaint is part of a recurring issue (at least 3 related to the same problem).
    """
    if len(past_complaints_texts) < 2:
        return {"is_recurring": False, "issue": "", "count": 1}
        
    prompt = f"""
لديك شكوى جديدة من نزيل، وقائمة ببعض الشكاوى الحديثة السابقة في الفندق.
الشكوى الجديدة: "{new_complaint}"
الشكاوى السابقة:
{chr(10).join([f"- {text}" for text in past_complaints_texts])}

هل تشير الشكوى الجديدة والشكاوى السابقة إلى نفس *الصنف* من المشاكل بشكل متكرر (مثال: مشاكل التكييف، النظافة، الإزعاج) بمجموع 3 مرات أو أكثر (بما فيها الشكوى الجديدة)؟
بمعنى: هل هناك مشكلة مزمنة أو متكررة تحتاج لفت انتباه الإدارة؟

أجب بـ JSON فقط:
{{
  "is_recurring": true/false,
  "issue": "اسم المشكلة باختصار شديد جداً (مثل: عطل المكيفات)",
  "count": "عدد المرات التقريبي الذي ذُكرت فيه المشكلة بما فيها الجديدة"
}}
"""
    try:
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt.strip()}],
            response_format={"type": "json_object"},
            max_completion_tokens=150,
        )
        return json.loads(response.choices[0].message.content.strip())
    except Exception as e:
        logger.error(f"Failed to detect recurring complaints: {e}")
        return {"is_recurring": False, "issue": "", "count": 1}
