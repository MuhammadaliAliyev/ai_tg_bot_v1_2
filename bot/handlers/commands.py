"""Command handlers for Aiogram bot (/start, /help, /clear)."""

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from loguru import logger

from bot.services.memory_service import memory_service

router = Router(name="commands_router")


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    """Handle /start command: Welcome user and explain bot multimodal capabilities."""
    user = message.from_user
    user_name = user.first_name if user else "Foydalanuvchi"

    text = (
        f"Assalomu alaykum, <b>{user_name}</b>!\n\n"
        "Men <b>Google Gemini AI</b> asosida ishlovchi aqlli yordamchingizman. "
        "Siz bilan quyidagi yo'nalishlarda samarali ishlay olaman:\n\n"
        "💬 <b>Matnli suhbat</b> — Savollaringizga batafsil javob beraman va suhbat kontekstini eslab qolaman.\n"
        "🖼 <b>Rasm tahlili</b> — Rasm yuboring va unga izoh bering (yoki bo'sh qoldiring), men uni tahlil qilib beraman.\n"
        "🎙 <b>Ovozli va audio xabarlar</b> — Ovozli xabar (.ogg) yoki audio fayl (.mp3, .wav) yuboring, uni tinglab javob qaytaraman.\n"
        "📄 <b>Hujjatlar</b> — PDF, TXT, CSV, JSON va dasturlash kodlari tahlili.\n\n"
        "<b>Mavjud buyruqlar:</b>\n"
        "• /clear — Suhbat tarixini tozalash va yangi mavzuni boshlash.\n"
        "• /help — Botdan foydalanish bo'yicha yo'riqnoma."
    )
    logger.info(f"Yangi /start buyrug'i: user_id={message.from_user.id if message.from_user else 'None'}")
    await message.answer(text, parse_mode="HTML")


@router.message(Command("help"))
async def handle_help(message: Message) -> None:
    """Handle /help command: Guide the user on capabilities and best practices."""
    help_text = (
        "📖 <b>Botdan foydalanish bo'yicha qo'llanma:</b>\n\n"
        "1️⃣ <b>Savol-javob:</b> Har qanday savolni to'g'ridan-to‘g‘ri yozing. Oldingi xabarlaringiz inobatga olinadi.\n"
        "2️⃣ <b>Rasmlar:</b> Rasm yuborishda caption (izoh) qo'shishingiz yoki shunchaki rasmni o'zini yuborishingiz mumkin.\n"
        "3️⃣ <b>Audio va Ovoz:</b> Ovozli xabaringizda savolingizni bering, Gemini uni eshitib javob beradi.\n"
        "4️⃣ <b>Fayllar:</b> PDF, matnli fayllar yoki kod fayllarini yuboring va nima qilish kerakligini yozing.\n"
        "5️⃣ <b>Xotirani tozalash:</b> Yangi mavzuga o'tmoqchi bo'lsangiz, /clear buyrug'idan foydalaning.\n\n"
        "<i>Eslatma: Maksimal fayl hajmi cheklovi — 20 MB.</i>"
    )
    await message.answer(help_text, parse_mode="HTML")


@router.message(Command("clear"))
async def handle_clear(message: Message) -> None:
    """Handle /clear command: Clear in-memory conversation turns for the user."""
    if message.from_user:
        user_id = message.from_user.id
        turn_count = memory_service.count(user_id)
        memory_service.clear_history(user_id)
        logger.info(f"Suhbat tozalandi: user_id={user_id}, o'chirilgan turnlar={turn_count}")
        await message.answer(
            "🧹 <b>Suhbat tarixi tozalandi!</b>\n\n"
            "Yangi mavzuni boshlashimiz mumkin. Sizni tinglayapman!",
            parse_mode="HTML",
        )
    else:
        await message.answer("Foydalanuvchi aniqlanmadi.")
