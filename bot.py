import os
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import gspread
from google.oauth2.service_account import Credentials

# ===========================================
# LOGGER AYARLARI
# ===========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

logger.info("=" * 60)
logger.info("🤖 SAHA ZİYARET BOT BAŞLATILIYOR...")
logger.info("=" * 60)

# ===========================================
# ENVIRONMENT VARIABLES
# ===========================================
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '8351485945:AAHTEv5C2RLdQtR9NtyZI_qPUwVWcv1orog')
GOOGLE_SHEET_NAME = os.getenv('GOOGLE_SHEET_NAME', 'Deren Kimya Saha Ziyaret Optimizasyonu')

# ===========================================
# GOOGLE SHEETS BAĞLANTISI
# ===========================================
def get_google_sheet():
    """Google Sheets'e bağlan"""
    try:
        # Credentials JSON'ı environment variable'dan al
        import json
        creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
        
        if not creds_json:
            logger.error("❌ GOOGLE_CREDENTIALS_JSON bulunamadı!")
            return None
        
        creds_dict = json.loads(creds_json)
        
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        sheet = client.open(GOOGLE_SHEET_NAME).sheet1
        
        logger.info("✅ Google Sheets bağlantısı başarılı")
        return sheet
        
    except Exception as e:
        logger.error(f"❌ Google Sheets bağlantı hatası: {e}")
        return None

# ===========================================
# KONUM KAYDETME
# ===========================================
def save_location_to_sheets(telegram_id: int, user_name: str, latitude: float, longitude: float, phone: str = None):
    """Konumu Google Sheets'e kaydet"""
    try:
        sheet = get_google_sheet()
        if not sheet:
            logger.error("❌ Sheet bağlantısı yok")
            return False
        
        # Tarih/saat
        timestamp = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        
        # Google Maps linki
        google_maps_url = f"https://www.google.com/maps?q={latitude},{longitude}"
        
        # Yeni satır
        row = [
            timestamp,           # A: Tarih/Saat
            user_name,          # B: Mühendis Adı
            str(telegram_id),   # C: Telegram ID
            phone or "",        # D: Telefon
            str(latitude),      # E: Enlem
            str(longitude),     # F: Boylam
            google_maps_url,    # G: Google Maps Link
            ""                  # H: Müşteri (boş)
        ]
        
        sheet.append_row(row)
        logger.info(f"✅ Konum kaydedildi: {user_name} | {latitude},{longitude}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Konum kaydetme hatası: {e}")
        return False

# ===========================================
# TELEGRAM BOT KOMUTLARI
# ===========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start komutu"""
    user_name = update.effective_user.full_name
    telegram_id = update.effective_user.id
    
    logger.info(f"👤 /start komutu: {user_name} (ID: {telegram_id})")
    
    await update.message.reply_text(
        f"✅ Merhaba {user_name}!\n\n"
        "Saha ziyareti sırasında konumunuzu paylaşabilirsiniz.\n\n"
        "📍 Telegram'ın konum paylaşma özelliğini kullanarak "
        "anlık konumunuzu gönderin.\n\n"
        "Konumunuz kaydedilecek ve yöneticileriniz tarafından görülebilecek."
    )

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Konum mesajlarını işle"""
    telegram_id = update.effective_user.id
    user_name = update.effective_user.full_name
    phone = update.effective_user.username
    
    logger.info(f"📍 Konum alındı: {user_name} (ID: {telegram_id})")
    
    # Konum bilgilerini al
    location = update.message.location
    latitude = location.latitude
    longitude = location.longitude
    
    # Google Sheets'e kaydet
    success = save_location_to_sheets(telegram_id, user_name, latitude, longitude, phone)
    
    if success:
        google_maps_url = f"https://www.google.com/maps?q={latitude},{longitude}"
        await update.message.reply_text(
            f"✅ Konum başarıyla kaydedildi!\n\n"
            f"👤 {user_name}\n"
            f"📍 {latitude}, {longitude}\n"
            f"🗺️ {google_maps_url}\n\n"
            f"Teşekkürler! 🙏"
        )
    else:
        await update.message.reply_text(
            "❌ Konum kaydedilemedi.\n\n"
            "Lütfen tekrar deneyin veya sistem yöneticisiyle iletişime geçin."
        )

# ===========================================
# ANA FONKSİYON
# ===========================================
def main():
    """Bot'u başlat"""
    logger.info("🚀 Bot başlatılıyor...")
    logger.info("📝 Mod: Herkes konum gönderebilir (Whitelist kontrolü YOK)")
    logger.info("✅ Güvenlik: Admin panel senkronizasyonunda yapılacak")
    
    # Application oluştur
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Handler'ları ekle
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.LOCATION, handle_location))
    
    # Bot'u çalıştır
    logger.info("✅ Bot çalışıyor ve konum bekliyor...")
    logger.info("=" * 60)
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
