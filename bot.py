import os
import telebot
from tvscreener import CryptoScreener, CryptoField

# Paste your BotFather token here or set it as an environment variable
BOT_TOKEN = os.getenv("BOT_TOKEN", "PASTE_YOUR_TELEGRAM_BOT_TOKEN_HERE")

bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    help_text = (
        "🤖 *Crypto Technical Screener Bot*\n\n"
        "Send me a coin ticker to get a full multi-timeframe CSV analysis.\n\n"
        "*Usage:*\n"
        "• `/scan BTC` (searches highest-volume exchange automatically)\n"
        "• `/scan QANX GATE` (targets Gate.io specifically)\n"
        "• `/scan SOL BINANCE` (targets Binance specifically)"
    )
    bot.reply_to(message, help_text, parse_mode="Markdown")

@bot.message_handler(commands=['scan', 'csv'])
def handle_scan(message):
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "⚠️ *Missing ticker.*\nExample usage: `/scan BTC` or `/scan QANX GATE`", parse_mode="Markdown")
        return

    symbol = args[1].strip().upper()
    pref_exchange = args[2].strip().upper() if len(args) > 2 else ""
    pair = symbol if symbol.endswith("USDT") else f"{symbol}USDT"

    status_msg = bot.reply_to(message, f"🔎 Searching TradingView for `{pair}`...", parse_mode="Markdown")
    filename = None

    try:
        # 1. Locate Pair
        lookup = CryptoScreener()
        lookup.where(CryptoField.NAME == pair)
        lookup.select(CryptoField.NAME, CryptoField.PRICE, CryptoField.EXCHANGE, CryptoField.VOLUME)
        lookup.sort_by(CryptoField.VOLUME, ascending=False)
        candidates = lookup.get()

        if candidates is None or candidates.empty:
            bot.edit_message_text(f"❌ Pair `{pair}` not found on TradingView.", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
            return

        # 2. Select Exchange
        if pref_exchange:
            matched = candidates[candidates['Exchange'].str.upper().str.contains(pref_exchange)]
            target = matched.iloc[0] if not matched.empty else candidates.iloc[0]
        else:
            target = candidates.iloc[0]

        ex = target['Exchange']
        name = target['Name']
        price = target['Price']

        bot.edit_message_text(
            f"⏳ Found *{ex}:{name}* (${price:,.6f}).\nExtracting ~3,500+ indicators across all timeframes...",
            chat_id=message.chat.id,
            message_id=status_msg.message_id,
            parse_mode="Markdown"
        )

        # 3. Pull All Multi-Timeframe Fields
        cs = CryptoScreener()
        cs.where(CryptoField.EXCHANGE == ex)
        cs.where(CryptoField.NAME == name)
        cs.select_all()
        df = cs.get()

        # 4. Save to Disk
        filename = f"{ex}_{name}_all_timeframes.csv"
        df.to_csv(filename, index=False)

        # 5. Send Document
        with open(filename, 'rb') as doc:
            bot.send_document(
                message.chat.id,
                doc,
                caption=f"✅ *{ex}:{name}*\n📊 Extracted {df.shape[1]} technical indicators.\n💰 Last Price: ${price}",
                parse_mode="Markdown"
            )

        bot.delete_message(message.chat.id, status_msg.message_id)

    except Exception as e:
        bot.edit_message_text(f"⚠️ *Error during extraction:*\n`{str(e)}`", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")

    finally:
        # Clean up disk space
        if filename and os.path.exists(filename):
            os.remove(filename)

print("Bot is running...")
bot.infinity_polling()
