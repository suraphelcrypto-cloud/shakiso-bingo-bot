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
