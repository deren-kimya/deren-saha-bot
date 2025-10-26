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
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
GOOGLE_SHEET_NAME = os.getenv('GOOGLE_SHEET_NAME', 'Deren Kimya Saha Ziyaret Optimizasyonu')
ADMIN_TELEGRAM_IDS = os.getenv('ADMIN_TELEGRAM_IDS', '410711923').split(',')

# ===========================================
# GOOGLE SHEETS BAĞLANTISI
# ===========================================
def get_google_sheet():
    """Google Sheets'e bağlan"""
    try:
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
        
        timestamp = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        google_maps_url = f"https://www.google.com/maps?q={latitude},{longitude}"
        
        row = [
            timestamp,
            user_name,
            str(telegram_id),
            phone or "",
            str(latitude),
            str(longitude),
            google_maps_url,
            ""
        ]
        
        sheet.append_row(row)
        logger.info(f"✅ Konum kaydedildi: {user_name} | {latitude},{longitude}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Konum kaydetme hatası: {e}")
        return False

# ===========================================
# SHEETS TEMİZLEME (ADMIN)
# ===========================================
def clear_sheets_data():
    """Google Sheets'teki tüm veriyi temizle (başlık hariç)"""
    try:
        sheet = get_google_sheet()
        if not sheet:
            logger.error("❌ Sheet bağlantısı yok")
            return False
        
        all_rows = sheet.get_all_values()
        if len(all_rows) > 1:
            sheet.delete_rows(2, len(all_rows))
            logger.info(f"✅ {len(all_rows) - 1} satır silindi")
            return True
        else:
            logger.info("ℹ️ Silinecek veri yok")
            return True
        
    except Exception as e:
        logger.error(f"❌ Sheets temizleme hatası: {e}")
        return False

# ===========================================
# ADMIN KONTROL
# ===========================================
def is_admin(telegram_id: int) -> bool:
    """Kullanıcı admin mi kontrol et"""
    return str(telegram_id) in ADMIN_TELEGRAM_IDS

# ===========================================
# TELEGRAM BOT KOMUTLARI
# ===========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start komutu"""
    user_name = update.effective_user.full_name
    telegram_id = update.effective_user.id
    
    logger.info(f"👤 /start komutu: {user_name} (ID: {telegram_id})")
    
    message = (
        f"✅ Merhaba {user_name}!\n\n"
        "Saha ziyareti sırasında konumunuzu paylaşabilirsiniz.\n\n"
        "📍 Telegram'ın konum paylaşma özelliğini kullanarak "
        "anlık konumunuzu gönderin.\n\n"
        "Konumunuz kaydedilecek ve yöneticileriniz tarafından görülebilecek."
    )
    
    if is_admin(telegram_id):
        message += "\n\n🔧 Admin Komutları:\n"
        message += "/clear - Sheets'teki tüm veriyi temizle\n"
        message += "/count - Kayıtlı konum sayısı"
    
    await update.message.reply_text(message)

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Konum mesajlarını işle"""
    telegram_id = update.effective_user.id
    user_name = update.effective_user.full_name
    phone = update.effective_user.username
    
    logger.info(f"📍 Konum alındı: {user_name} (ID: {telegram_id})")
    
    location = update.message.location
    latitude = location.latitude
    longitude = location.longitude
    
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

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sheets'i temizle (sadece admin)"""
    telegram_id = update.effective_user.id
    user_name = update.effective_user.full_name
    
    logger.info(f"🗑️ /clear komutu: {user_name} (ID: {telegram_id})")
    
    if not is_admin(telegram_id):
        await update.message.reply_text("❌ Bu komutu kullanma yetkiniz yok!")
        logger.warning(f"⚠️ Yetkisiz /clear denemesi: {user_name} (ID: {telegram_id})")
        return
    
    await update.message.reply_text(
        "⚠️ DİKKAT!\n\n"
        "Google Sheets'teki TÜM VERİLER silinecek!\n\n"
        "Devam etmek için /clearconfirm yazın."
    )

async def clear_confirm_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sheets temizleme onayı (sadece admin)"""
    telegram_id = update.effective_user.id
    user_name = update.effective_user.full_name
    
    logger.info(f"🗑️ /clearconfirm komutu: {user_name} (ID: {telegram_id})")
    
    if not is_admin(telegram_id):
        await update.message.reply_text("❌ Bu komutu kullanma yetkiniz yok!")
        return
    
    await update.message.reply_text("⏳ Veriler temizleniyor...")
    
    success = clear_sheets_data()
    
    if success:
        await update.message.reply_text(
            "✅ Google Sheets başarıyla temizlendi!\n\n"
            "Tüm konum kayıtları silindi."
        )
        logger.info(f"✅ Sheets temizlendi (Admin: {user_name})")
    else:
        await update.message.reply_text(
            "❌ Temizleme sırasında hata oluştu!\n\n"
            "Lütfen sistem yöneticisiyle iletişime geçin."
        )

async def count_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kayıtlı konum sayısını göster (sadece admin)"""
    telegram_id = update.effective_user.id
    user_name = update.effective_user.full_name
    
    logger.info(f"📊 /count komutu: {user_name} (ID: {telegram_id})")
    
    if not is_admin(telegram_id):
        await update.message.reply_text("❌ Bu komutu kullanma yetkiniz yok!")
        return
    
    try:
        sheet = get_google_sheet()
        if not sheet:
            await update.message.reply_text("❌ Sheet bağlantısı kurulamadı!")
            return
        
        all_rows = sheet.get_all_values()
        count = len(all_rows) - 1
        
        await update.message.reply_text(
            f"📊 İstatistikler\n\n"
            f"Toplam Kayıt: {count}\n"
            f"Sheet: {GOOGLE_SHEET_NAME}"
        )
        
    except Exception as e:
        logger.error(f"❌ Count hatası: {e}")
        await update.message.reply_text("❌ İstatistik alınırken hata oluştu!")

# ===========================================
# ANA FONKSİYON
# ===========================================
def main():
    """Bot'u başlat"""
    logger.info("🚀 Bot başlatılıyor...")
    logger.info("📝 Mod: Herkes konum gönderebilir")
    logger.info(f"🔧 Admin Telegram IDs: {ADMIN_TELEGRAM_IDS}")
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(CommandHandler("clearconfirm", clear_confirm_command))
    application.add_handler(CommandHandler("count", count_command))
    application.add_handler(MessageHandler(filters.LOCATION, handle_location))
    
    logger.info("✅ Bot çalışıyor ve konum bekliyor...")
    logger.info("=" * 60)
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
