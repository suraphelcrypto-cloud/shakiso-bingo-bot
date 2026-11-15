import asyncio
import random
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Bot Token ከ BotFather ያገኘኸው
BOT_TOKEN = "9067120273:AAuL_Zft27eZiHzTzBYPF1e2Q9q89Xw5gc"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ----------------- DB SETUP -----------------
conn = sqlite3.connect("bingo_game.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    balance REAL DEFAULT 0.0
)
""")
conn.commit()

# ----------------- GAME STATE -----------------
active_game = {
    "is_running": False,
    "bet_amount": 5,
    "players": {},
    "called_numbers": [],
}

# ----------------- HELPER FUNCTIONS -----------------
def generate_bingo_card():
    numbers = random.sample(range(1, 76), 25)
    card = [numbers[i : i + 5] for i in range(0, 25, 5)]
    card[2][2] = "FREE"
    return card

def get_user_balance(user_id):
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    return res[0] if res else 0.0

def update_user_balance(user_id, amount):
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()

def check_bingo(player_card, called_numbers):
    marked_grid = []
    for row in player_card:
        row_status = []
        for cell in row:
            if cell == "FREE" or cell in called_numbers:
                row_status.append(True)
            else:
                row_status.append(False)
        marked_grid.append(row_status)

    size = 5
    for row in marked_grid:
        if all(row): return True
    for col in range(size):
        if all(marked_grid[row][col] for row in range(size)): return True
    if all(marked_grid[i][i] for i in range(size)): return True
    if all(marked_grid[i][size - 1 - i] for i in range(size)): return True

    return False

# ----------------- BOT HANDLERS -----------------
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()

    balance = get_user_balance(user_id)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💰 ሒሳብ ማስገባት (Deposit)", callback_data="deposit"),
                InlineKeyboardButton(text="ወደ ውጭ ማውጣት (Withdraw)", callback_data="withdraw"),
            ],
            [
                InlineKeyboardButton(text="🎮 በ 5 ብር ተጫወት", callback_data="join_5"),
                InlineKeyboardButton(text="🎮 በ 10 ብር ተጫወት", callback_data="join_10"),
            ],
            [
                InlineKeyboardButton(text="📊 የኔ ሒሳብ (Balance)", callback_data="check_balance")
            ],
        ]
    )

    await message.answer(
        f"🎲 **እንኳን ወደ ሻኪሶ ጎልድ ቢንጎ በደህና መጡ!**\n\n"
        f"👤 ተጫዋች: {username}\n"
        f"💳 የሂሳብ መጠን: {balance:.2f} ETB\n\n"
        f"📌 **ህጎች:**\n"
        f"- ዝቅተኛ ገቢ/ወጪ ሒሳብ: 50 ብር\n"
        f"- የውርርድ መጠን: 5 ብር ወይም 10 ብር\n"
        f"- ቁጥሮች: ከ 1 እስከ 75",
        reply_markup=kb,
    )

@dp.callback_query(F.data == "check_balance")
async def balance_handler(callback: types.CallbackQuery):
    balance = get_user_balance(callback.from_user.id)
    await callback.answer(f"የእርስዎ ሂሳብ: {balance:.2f} ብር ነው", show_alert=True)

@dp.callback_query(F.data == "deposit")
async def deposit_handler(callback: types.CallbackQuery):
    await callback.message.answer(
        "💳 **ሒሳብ ለመሙላት:**\n\n"
        "1. ቢያንስ 50 ብር በ Telebirr/CBE ወደ አካውንታችን ያስተላልፉ።\n"
        "2. የክፍያ ማረጋገጫ (Receipt/Transaction ID) ለአድሚን ይላኩ።"
    )
    await callback.answer()

@dp.callback_query(F.data.in_(["join_5", "join_10"]))
async def join_game(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    bet = 5 if callback.data == "join_5" else 10
    balance = get_user_balance(user_id)

    if balance < bet:
        await callback.answer("⚠️ የሂሳብዎ መጠን በቂ አይደለም! (ዝቅተኛ ውርርድ 5/10 ብር)", show_alert=True)
        return

    update_user_balance(user_id, -bet)
    card = generate_bingo_card()
    active_game["bet_amount"] = bet
    active_game["players"][user_id] = {"card": card}

    card_str = "\n".join(["\t".join(map(str, row)) for row in card])
    await callback.message.answer(
        f"✅ በ {bet} ብር ተመዝግበዋል!\n\n📋 **የእርስዎ ካርቴላ:**\n`{card_str}`\n\n"
        f"ግሩፕ ውስጥ 'bingo' በማለት ማሸነፍዎን ማረጋገጥ ይችላሉ።",
        parse_mode="Markdown",
    )
    await callback.answer()

@dp.message(Command("start_bingo"))
async def start_bingo_game(message: types.Message):
    if active_game["is_running"]:
        await message.answer("ጨዋታው አሁን ላይ እየተካሄደ ነው!")
        return

    if len(active_game["players"]) < 1:
        await message.answer("ጨዋታውን ለመጀመር ቢያንስ ተጫዋቾች መመዝገብ አለባቸው!")
        return

    active_game["is_running"] = True
    active_game["called_numbers"] = []

    await message.answer("🎲 **የቢንጎ ጨዋታ ተጀምሯል!** ቁጥሮች (ከ 1 እስከ 75) መጠራት ይጀምራሉ።")

    available_numbers = list(range(1, 76))
    random.shuffle(available_numbers)

    for num in available_numbers:
        if not active_game["is_running"]:
            break

        active_game["called_numbers"].append(num)

        await message.answer(
            f"🔔 የወጣው ቁጥር: **{num}**\n"
            f"የወጡ ቁጥሮች ብዛት: {len(active_game['called_numbers'])}/75",
            parse_mode="Markdown",
        )
        await asyncio.sleep(5)

    active_game["is_running"] = False
    await message.answer("🏁 ጨዋታው ተጠናቋል!")

@dp.message(F.text.lower() == "bingo")
async def verify_player_bingo(message: types.Message):
    user_id = message.from_user.id

    if not active_game["is_running"] or user_id not in active_game["players"]:
        await message.answer("⚠️ አሁን ንቁ ጨዋታ የለም ወይም በጨዋታው ውስጥ የለህም!")
        return

    player_card = active_game["players"][user_id]["card"]
    called_numbers = active_game["called_numbers"]

    is_winner = check_bingo(player_card, called_numbers)

    if is_winner:
        active_game["is_running"] = False
        winner_name = message.from_user.first_name
        bet_amount = active_game["bet_amount"]
        total_players = len(active_game["players"])

        total_pool = total_players * bet_amount
        winner_prize = total_pool * 0.80
        house_commission = total_pool * 0.20

        update_user_balance(user_id, winner_prize)

        await message.answer(
            f"🎉 **እንኳን ደስ አለዎት! {winner_name} ቢንጎ (BINGO) ሆኗል!** 🏆\n\n"
            f"👥 ጠቅላላ ተጫዋቾች: {total_players} ሰው\n"
            f"💰 ጠቅላላ ገቢ: {total_pool:.2f} ብር\n"
            f"🎁 ለአሸናፊው የተሰጠ (80%): **{winner_prize:.2f} ብር**\n\n"
            f"💳 ገንዘቡ በራስ-ሰር ወደ ሂሳብዎ ገብቷል!",
            parse_mode="Markdown"
        )

        active_game["players"] = {}
        active_game["called_numbers"] = []
    else:
        await message.answer("❌ **ሀሰተኛ ጥሪ (False Bingo)!** ካርቴላዎ እስካሁን ሙሉ መስመር አልሞላም።")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    import asyncio
import logging
import os
import random
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

TOKEN = os.getenv("BOT_TOKEN", "9067120273:AAuL_Zft27eZiHzTzBYPF1e2Q9q89Xw5gc")

bot = Bot(token=TOKEN)
dp = Dispatcher()

def get_main_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎮 ጨዋታ ጀምር (Play)", callback_data="play_menu")],
            [InlineKeyboardButton(text="💰 የእኔ ቀሪ ሂሳብ", callback_data="balance"),
             InlineKeyboardButton(text="📥 ገንዘብ ማስገባት", callback_data="deposit")],
            [InlineKeyboardButton(text="📤 ገንዘብ ማውጣት", callback_data="withdraw")],
            [InlineKeyboardButton(text="📋 አጠቃቀም መመሪያ", callback_data="instructions")]
        ]
    )

def get_rooms_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎮 ጨዋታ | 5 ብር", callback_data="room_5")],
            [InlineKeyboardButton(text="🎮 ጨዋታ | 10 ብር", callback_data="room_10")],
            [InlineKeyboardButton(text="🔙 ወደ ዋናው ሜኑ", callback_data="back_to_main")]
        ]
    )

def generate_bingo_card():
    # 5x5 የቢንጎ ካርድ በዘፈቀደ ቁጥሮች ማመንጨት
    card = []
    for _ in range(5):
        row = [str(random.randint(1, 75)) for _ in range(5)]
        card.append(" | ".join(row))
    return "\n---------------------\n".join(card)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    welcome_text = (
        "✨ **ወደ Shakiso Gold Bingo በደህና መጡ!** ✨\n\n"
        "በሞባይል ስልክዎ እየተዝናኑ የሚሸለሙበት አስደሳች የቢንጎ ጨዋታ። "
        "እባክዎ ከታች ከሚገኙት አማራጮች የሚፈልጉትን ይምረጡ!"
    )
    await message.answer(welcome_text, parse_mode="Markdown", reply_markup=get_main_menu())

@dp.message(Command("play"))
async def cmd_play(message: types.Message):
    await message.answer("👇 እባክዎ ለመጫወት የሚፈልጉትን ክፍል (Room) ይምረጡ:", reply_markup=get_rooms_menu())

@dp.callback_query(F.data == "play_menu")
async def process_play_menu(callback: types.CallbackQuery):
    await callback.message.edit_text("👇 እባክዎ ለመጫወት የሚፈልጉትን ክፍል (Room) ይምረጡ:", reply_markup=get_rooms_menu())
    await callback.answer()

@dp.callback_query(F.data.in_({"room_5", "room_10"}))
async def process_room_selection(callback: types.CallbackQuery):
    room_name = "5 ብር" if callback.data == "room_5" else "10 ብር"
    card = generate_bingo_card()
    
    game_text = (
        f"🎟️ **የ Shakiso Gold Bingo ካርድዎ ({room_name})**\n\n"
        f"{card}\n\n"
        "⏳ ጨዋታው ሊጀመር ነው... እባክዎ ይጠብቁ!"
    )
    
    back_markup = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 ወደ ክፍሎች ምርጫ", callback_data="play_menu")]]
    )
    
    await callback.message.edit_text(game_text, parse_mode="Markdown", reply_markup=back_markup)
    await callback.answer()

@dp.callback_query(F.data == "balance")
async def process_balance(callback: types.CallbackQuery):
    await callback.answer("💰 የእርስዎ ቀሪ ሂሳብ: 0.00 ብር", show_alert=True)

@dp.callback_query(F.data == "deposit")
async def process_deposit(callback: types.CallbackQuery):
    await callback.message.answer("📥 ገንዘብ ለማስገባት በቴሌብር (Telebirr) ወይም በባንክ አካውንት ይጠቀሙ።")
    await callback.answer()

@dp.callback_query(F.data == "withdraw")
async def process_withdraw(callback: types.CallbackQuery):
    await callback.message.answer("📤 ገንዘብ ለማውጣት `/withdraw` የሚለውን ትእዛዝ ይጠቀሙ።")
    await callback.answer()

@dp.callback_query(F.data == "instructions")
async def process_instructions(callback: types.CallbackQuery):
    instructions_text = (
        "📋 **የቢንጎ ጨዋታ መመሪያ:**\n\n"
        "1. ከ 5 ብር ወይም 10 ብር ክፍሎች አንዱን ይምረጡ።\n"
        "2. የቢንጎ ካርድ ይደርስዎታል።\n"
        "3. ቁጥሮች ሲጠሩ በካርድዎ ላይ ካሉ ይሞላሉ።\n"
        "4. መጀመሪያ ካርዱን የጨረሰ አሸናፊ ይሆናል!"
    )
    await callback.message.answer(instructions_text, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "back_to_main")
async def process_back(callback: types.CallbackQuery):
    await callback.message.edit_text("✨ **ዋና ሜኑ**:", reply_markup=get_main_menu())
    await callback.answer()

async def main():
    logging.basicConfig(level=logging.INFO)
    print("Bot is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

