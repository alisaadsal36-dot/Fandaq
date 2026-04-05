import imaplib
import email
from email.header import decode_header
import logging
import json
import re
import hashlib
import codecs
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import async_session_factory
from app.models.hotel import Hotel
from app.models.room_type import RoomType

logger = logging.getLogger(__name__)

class EmailAgentService:
    MAX_EMAILS_PER_POLL = 20

    IGNORED_SENDER_PATTERNS = (
        "no-reply@",
        "noreply@",
        "mailer-daemon@",
        "postmaster@",
    )

    @staticmethod
    def _decode_mime_header(value: str | None) -> str:
        parts = decode_header(value or "")
        decoded: list[str] = []
        for part, encoding in parts:
            if isinstance(part, bytes):
                enc = (encoding or "utf-8").strip().lower()
                if enc in {"unknown-8bit", "x-unknown", "unknown"}:
                    enc = "utf-8"
                try:
                    codecs.lookup(enc)
                except Exception:
                    enc = "utf-8"
                decoded.append(part.decode(enc, errors="replace"))
            else:
                decoded.append(part)
        return "".join(decoded).strip()

    @staticmethod
    def _decode_payload(payload: bytes | None, charset: str | None = None) -> str:
        if not payload:
            return ""
        candidates = [charset, "utf-8", "cp1256", "latin-1"]
        for enc in candidates:
            if not enc:
                continue
            try:
                return payload.decode(enc)
            except Exception:
                continue
        return payload.decode("utf-8", errors="replace")

    @staticmethod
    def _should_ignore_sender(sender_email: str | None) -> bool:
        if not sender_email:
            return True
        lowered = sender_email.strip().lower()
        return any(token in lowered for token in EmailAgentService.IGNORED_SENDER_PATTERNS)

    @staticmethod
    async def poll_and_process():
        """Polls for unread emails and processes replies."""
        settings = get_settings()
        if not settings.IMAP_ENABLED or not settings.SMTP_USER or not settings.SMTP_PASSWORD:
            return

        try:
            # Connect to IMAP
            mail = imaplib.IMAP4_SSL(settings.IMAP_HOST, settings.IMAP_PORT)
            mail.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            mail.select("inbox")

            # Process only unread emails to avoid scanning the whole mailbox every poll.
            status, messages = mail.search(None, 'UNSEEN')
            if status != 'OK':
                return

            # Avoid long-running polls when mailbox has many unread messages.
            email_ids = messages[0].split()[-EmailAgentService.MAX_EMAILS_PER_POLL:]
            for num in email_ids:
                status, data = mail.fetch(num, '(RFC822)')
                if status != 'OK':
                    continue

                for response_part in data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        message_id = msg.get("Message-ID")
                        if not message_id:
                            # Some providers omit Message-ID; use deterministic hash as fallback dedupe key.
                            raw_digest = hashlib.sha256(response_part[1]).hexdigest()
                            message_id = f"fallback-{raw_digest}"
                        
                        # Use ProcessedMessage to deduplicate
                        async with async_session_factory() as db:
                            from app.models.processed_message import ProcessedMessage
                            check_stmt = select(ProcessedMessage).where(ProcessedMessage.id == message_id)
                            res = await db.execute(check_stmt)
                            if res.scalar_one_or_none():
                                continue

                        subject = EmailAgentService._decode_mime_header(msg.get("Subject"))
                        
                        from_email = email.utils.parseaddr(msg["From"])[1]
                        if EmailAgentService._should_ignore_sender(from_email):
                            continue
                        
                        # Get body
                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                content_type = part.get_content_type()
                                content_disposition = str(part.get("Content-Disposition"))
                                if content_type == "text/plain" and "attachment" not in content_disposition:
                                    body = EmailAgentService._decode_payload(
                                        part.get_payload(decode=True),
                                        part.get_content_charset(),
                                    )
                                    break
                        else:
                            payload = msg.get_payload(decode=True)
                            if payload:
                                body = EmailAgentService._decode_payload(
                                    payload,
                                    msg.get_content_charset(),
                                )

                        if body:
                            # Process and then mark as processed
                            success = await EmailAgentService.process_email(from_email, subject, body)
                            if success or not success: # Mark regardless of success to avoid infinite loops on unparseable mail
                                async with async_session_factory() as db:
                                    db.add(ProcessedMessage(id=message_id))
                                    await db.commit()

            mail.logout()
        except Exception as e:
            logger.error(f"❌ EmailAgent IMAP Error: {e}")

    @staticmethod
    async def process_email(sender_email: str, subject: str, body: str):
        """Identifies hotel and processes the intent."""
        async with async_session_factory() as db:
            # 1. Identify Hotel by sender_email
            stmt = select(Hotel).where(Hotel.owner_email == sender_email)
            result = await db.execute(stmt)
            hotel = result.scalar_one_or_none()

            if not hotel:
                logger.debug(f"📩 EmailAgent: Owner not found, skipping sender: {sender_email}")
                return

            # 2. Extract Hidden Hotel ID
            hotel_id_match = re.search(r"\[HID:([a-f0-9\-]+)\]", body + subject)
            if hotel_id_match:
                extracted_id = hotel_id_match.group(1)
                if str(hotel.id) != extracted_id:
                    stmt = select(Hotel).where(Hotel.id == extracted_id, Hotel.owner_email == sender_email)
                    result = await db.execute(stmt)
                    hotel = result.scalar_one_or_none()
            
            if not hotel:
                return

            # 3. Use AI to parse intent
            intent = await EmailAgentService.parse_intent_with_ai(body, hotel.name)
            if not intent or intent.get("action") == "NONE":
                return

            # 4. Execute Action
            if intent["action"] == "UPDATE_PRICE":
                success = await EmailAgentService.execute_price_update(db, hotel, intent)
                if success:
                    logger.info(f"✅ EmailAgent: Successfully executed {intent['action']} for {hotel.name}")
                    await EmailAgentService.send_confirmation(hotel, intent)
                    return True
                else:
                    logger.warning(f"❌ EmailAgent: Failed to execute {intent['action']} for {hotel.name}")
                    return False
            
            return False

    @staticmethod
    async def parse_intent_with_ai(body: str, hotel_name: str):
        """Extracts intent from email body using OpenAI."""
        settings = get_settings()
        if not settings.OPENAI_API_KEY:
            return None

        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        prompt = (
            f"You are an AI manager for '{hotel_name}'. Analyze this email reply from the owner and extract the requested action.\n"
            f"Email Body: \"{body}\"\n\n"
            "Supported Actions:\n"
            "1. UPDATE_PRICE: Changing room rates.\n"
            "   Parameters:\n"
            "   - 'amount' (number): The value to change by. IMPORTANT: If the owner says 'reduce/decrease/خصم/قلل', 'amount' MUST BE NEGATIVE. If 'increase/add/زيادة', 'amount' MUST BE POSITIVE.\n"
            "   - 'is_relative' (bool): True if they use relative terms ('add 10', 'reduce 5'), False if they set an absolute price ('make it 500').\n"
            "   - 'room_type' (str): The name of the room type or 'ALL' if not specified.\n"
            "If no action is clear, return action: 'NONE'.\n\n"
            "Return ONLY a clean JSON object."
        )

        try:
            response = await client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"❌ EmailAgent AI Intent Parsing Error: {e}")
            return None

    @staticmethod
    async def execute_price_update(db: AsyncSession, hotel: Hotel, intent: dict):
        """Updates room prices in the database."""
        try:
            amount = intent.get("amount", 0)
            is_relative = intent.get("is_relative", True)
            room_type_name = intent.get("room_type", "ALL")

            stmt = select(RoomType).where(RoomType.hotel_id == hotel.id)
            if room_type_name != "ALL":
                # Basic matching for room type name
                stmt = stmt.where(RoomType.name.ilike(f"%{room_type_name}%"))
            
            result = await db.execute(stmt)
            room_types = result.scalars().all()

            if not room_types:
                return False

            for rt in room_types:
                if is_relative:
                    rt.daily_rate = float(rt.daily_rate) + amount
                else:
                    rt.daily_rate = amount
            
            # Also update DailyPricing for TODAY to reflect in Dashboard
            from app.models.daily_pricing import DailyPricing
            from datetime import date
            today = date.today()
            stmt_dp = select(DailyPricing).where(
                DailyPricing.hotel_id == hotel.id,
                DailyPricing.date == today
            )
            res_dp = await db.execute(stmt_dp)
            daily_prices = res_dp.scalars().all()
            
            for dp in daily_prices:
                if is_relative:
                    dp.my_price = float(dp.my_price) + amount
                else:
                    dp.my_price = amount
            
            await db.commit()
            logger.info(f"✅ EmailAgent: Updated prices in RoomTypes and DailyPricing for {hotel.name}")
            return True
        except Exception as e:
            logger.error(f"❌ EmailAgent Price Update Error: {e}")
            return False

    @staticmethod
    async def send_confirmation(hotel: Hotel, intent: dict):
        """Sends a confirmation email to the owner."""
        if not hotel.owner_email:
            logger.info(f"ℹ️ EmailAgent: owner_email is missing for {hotel.name}; skipping confirmation email")
            return

        amount = intent.get("amount", 0)
        is_relative = intent.get("is_relative", True)
        
        if is_relative:
            change_text = f"بمقدار {abs(amount)} ريال ({'زيادة' if amount > 0 else 'خصم'})"
        else:
            change_text = f"إلى {amount} ريال"

        message = (
            f"✅ تم تنفيذ طلبك لفندق *{hotel.name}* بنجاح!\n\n"
            f"تحديث الأسعار: {change_text}.\n"
            f"تم تحديث السعر في قاعدة البيانات وفي لوحة التحكم (Dashboard) فوراً.\n\n"
            "شكراً لاستخدامك RAHATY ✨"
        )

        # Send via Email
        try:
            from app.services.email_service import send_email_with_attachment
            await send_email_with_attachment(
                to_email=hotel.owner_email,
                subject=f"✅ تأكيد تحديث الأسعار - {hotel.name}",
                body_text=message,
            )
            logger.info(f"✅ EmailAgent: Confirmation email sent to {hotel.owner_email}")
        except Exception as e:
            logger.error(f"❌ EmailAgent: Failed to send confirmation email: {e}")
