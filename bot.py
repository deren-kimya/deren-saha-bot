import os
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Telegram Bot Token
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')

# Google Sheets Credentials
SHEET_ID = os.environ.get('SHEET_ID')
GOOGLE_CREDS = os.environ.get('GOOGLE_CREDENTIALS')

# Google Sheets bağlantısı
def get_sheet():
    try:
        creds_dict = json.loads(GOOGLE_CREDS)
        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SHEET_ID).sheet1
        return sheet
    except Exception as e:
        logger.error(f"Sheets bağlantı hatası: {e}")
        return None

# /start komutu
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 Deren Kimya Saha Takip Bot'a Hoş Geldiniz!\n\n"
        "📍 Konum göndermek için:\n"
        "1. Mesaj kutusundaki 📎 ikonuna tıklayın\n"
        "2. 'Konum' seçeneğini seçin\n"
        "3. Mevcut konumunuzu paylaşın\n\n"
        "✅ Konumunuz otomatik olarak kaydedilecektir."
    )

# Konum işleme
async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        location = update.message.location
        user = update.message.from_user
        timestamp = update.message.date
        
        # Konum bilgileri
        latitude = location.latitude
        longitude = location.longitude
        user_name = f"{user.first_name} {user.last_name if user.last_name else ''}".strip()
        user_id = user.id
        maps_link = f"https://www.google.com/maps?q={latitude},{longitude}"
        
        # Türkiye saati
        tr_time = timestamp.strftime('%d.%m.%Y %H:%M:%S')
        
        # Sheets'e yaz
        sheet = get_sheet()
        if sheet:
            sheet.append_row([
                tr_time,
                user_name,
                str(user_id),
                str(latitude),
                str(longitude),
                maps_link,
                '',  # Müşteri
                ''   # Notlar
            ])
            
            logger.info(f"✅ Konum kaydedildi: {user_name} - {maps_link}")
            
            # Onay mesajı
            await update.message.reply_text(
                f"✅ Konum kaydedildi!\n\n"
                f"📍 {maps_link}\n"
                f"🕐 {tr_time}"
            )
        else:
            await update.message.reply_text("❌ Sheets bağlantısı kurulamadı. Lütfen tekrar deneyin.")
            
    except Exception as e:
        logger.error(f"Konum işleme hatası: {e}")
        await update.message.reply_text("❌ Bir hata oluştu. Lütfen tekrar deneyin.")

# Metin mesajları
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❌ Sadece konum kabul edilmektedir.\n\n"
        "📍 Konum göndermek için mesaj kutusundaki 📎 ikonuna tıklayın."
    )

# Ana fonksiyon
def main():
    # Bot oluştur
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Handler'lar
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.LOCATION, handle_location))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    # Botu başlat
    logger.info("🤖 Bot başlatılıyor...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()