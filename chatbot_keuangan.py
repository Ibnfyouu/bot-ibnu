# chatbot_keuangan_final.py
import os
from datetime import datetime
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ---------- CONFIG ----------
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")  # atau langsung isi manual
SHEET_ID = os.getenv("SHEET_ID")
CRED_FILE = "chatbotsheet-477809-9092aaafe5bf.json"

INPUT_DATA = 0

# ---------- GOOGLE SHEET ----------
SCOPE = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(CRED_FILE, SCOPE)
gc = gspread.authorize(creds)

sheet1 = gc.open_by_key(SHEET_ID).sheet1      # Sheet utama
sheet2 = gc.open_by_key(SHEET_ID).get_worksheet(1)  # Sheet 2

# ---------- DAFTAR KATEGORI & SALDO ----------
KATEGORI_DICT = {
    "1": "Makanan",
    "2": "Perawatan & Kesehatan",
    "3": "Transportasi",
    "4": "Kebutuhan Pendidikan",
    "5": "Bayar Sewa Kost",
    "6": "Lainnya",
    "7": "Gaji",
    "8": "Honor",
    "9": "Ngojek",
}

WALLET_DICT = {
    "1": "Cash",
    "2": "ShopeePay",
    "3": "GoPay",
    "4": "Dana",
    "5": "Mandiri",
    "6": "BCA",
    "7": "BRI",
}

def tipe_from_category_id(cat_id: str) -> str:
    return "Masuk" if cat_id in {"7", "8", "9"} else "Keluar"

# ---------- HELPER ----------
def parse_line(line: str):
    parts = [p.strip() for p in line.split(",")]
    if len(parts) != 4:
        raise ValueError("Format harus: deskripsi, kategori_nomor, nominal, saldo_nomor")
    deskripsi, cat_id, nominal_s, saldo_id = parts
    if cat_id not in KATEGORI_DICT:
        raise ValueError(f"Kategori tidak valid: {cat_id}")
    if saldo_id not in WALLET_DICT:
        raise ValueError(f"Saldo_ke tidak valid: {saldo_id}")
    nominal = float(nominal_s.replace(",", "").replace("Rp", "").strip())
    return deskripsi, cat_id, nominal, saldo_id

def append_row_sheet1(tgl, kategori, deskripsi, nominal, wallet, tipe, uid, uname):
    sheet1.append_row([tgl, kategori, deskripsi, nominal, wallet, tipe, uid, uname], value_input_option="USER_ENTERED")

# ---------- HANDLERS ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 Halo! Ini *Bot Keuangan Project12*.\n\n"
        "Ketik `/input` untuk input transaksi.\n"
        "Ketik `/laporan` untuk lihat pengeluaran harian.\n"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def cmd_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kategori_text = "🧾 *Daftar Kategori:*\n" + "\n".join([f"{k}. {v}" for k, v in KATEGORI_DICT.items()])
    wallet_text = "\n\n💰 *Daftar Saldo:*\n" + "\n".join([f"{k}. {v}" for k, v in WALLET_DICT.items()])
    format_text = (
        "\n\nKirim data transaksi dengan format:\n"
        "`deskripsi, kategori_nomor, nominal, saldo_nomor`\n"
        "Contoh: `mie ayam, 1, 15000, 2`"
    )
    await update.message.reply_text(kategori_text + wallet_text + format_text, parse_mode="Markdown")
    return INPUT_DATA

async def handle_input_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    text = update.message.text.strip()
    lines = [l for l in text.splitlines() if l.strip()]
    added, errors = 0, []
    now = datetime.now().strftime("%d/%m/%Y")

    for i, line in enumerate(lines, 1):
        try:
            deskripsi, cat_id, nominal, saldo_id = parse_line(line)
            append_row_sheet1(now, KATEGORI_DICT[cat_id], deskripsi, nominal, WALLET_DICT[saldo_id], tipe_from_category_id(cat_id), user.id, user.username or user.first_name)
            added += 1
        except Exception as e:
            errors.append(f"Baris {i}: {e}")

    reply = f"✅ {added} transaksi berhasil ditambahkan."
    if errors:
        reply += "\n\n⚠️ Error:\n" + "\n".join(errors)
    await update.message.reply_text(reply)
    return ConversationHandler.END

async def laporan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    values = sheet2.get("C18:G30")
    if not values:
        await update.message.reply_text("❌ Tidak ada data pengeluaran di Sheet 2.")
        return

    msg = "📊 *Laporan Pengeluaran Hari Ini:*\n\n"
    total_keluar = 0

    for row in values:
        if len(row) < 4:
            continue
        kategori, deskripsi, nominal_str, saldo = row[:4]
        nominal = int(nominal_str.replace("Rp", "").replace(".", "").replace(",", "").strip())
        if kategori.lower() != "gaji":
            total_keluar += nominal
        msg += f"{kategori} - {deskripsi}: Rp{nominal:,} ({saldo})\n"

    msg += f"\n💸 *Total Pengeluaran:* Rp{total_keluar:,}"
    await update.message.reply_text(msg, parse_mode="Markdown")

# ---------- MAIN ----------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("input", cmd_input)],
        states={INPUT_DATA: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_input_data)]},
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.add_handler(CommandHandler("laporan", laporan))

    print("🤖 Bot keuangan Project12 siap digunakan...")
    app.run_polling()

if __name__ == "__main__":
    main()
